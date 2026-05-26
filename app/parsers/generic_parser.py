from __future__ import annotations
import re
from datetime import datetime
from typing import Optional

from app.core.models import LogEntry
from app.parsers.base_parser import BaseParser

# Timestamp patterns ordered by specificity
_TS_PATTERNS = [
    # ISO 8601 with ms/tz
    re.compile(
        r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
    ),
    # dd/Mon/yyyy:HH:MM:SS tz  (Apache)
    re.compile(r"(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}\s[+-]\d{4})"),
    # Mon dd HH:MM:SS  (syslog)
    re.compile(r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"),
    # dd/mm/yyyy HH:MM:SS
    re.compile(r"(\d{2}[/\-]\d{2}[/\-]\d{4}\s+\d{2}:\d{2}:\d{2})"),
    # yyyy/mm/dd HH:MM:SS
    re.compile(r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})"),
    # epoch seconds (10 digits)
    re.compile(r"\b(\d{10})\b"),
]

_LEVEL_RE = re.compile(
    r"\b(TRACE|DEBUG|INFO(?:RMATION)?|NOTICE|WARN(?:ING)?|ERROR|ERR|"
    r"CRITICAL|CRIT|FATAL|EMERG|ALERT|SEVERE)\b",
    re.IGNORECASE,
)

_TS_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%d/%b/%Y:%H:%M:%S %z",
    "%b %d %H:%M:%S",
    "%b  %d %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",   # American: MM/DD/YYYY (try before DD/MM to handle day>12)
    "%d/%m/%Y %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
]


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    ts_str = ts_str.strip()
    # strip trailing timezone offsets not supported by strptime
    ts_clean = re.sub(r"[+-]\d{2}:?\d{2}$", "", ts_str).rstrip("Z").strip()
    ts_clean = ts_clean.replace(",", ".")

    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(ts_clean, fmt)
        except ValueError:
            continue

    # Inject current year for month-day-only syslog timestamps
    if re.match(r'^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}$', ts_clean):
        from datetime import date
        ts_clean = f"{date.today().year} {ts_clean}"
        for fmt in ["%Y %b %d %H:%M:%S", "%Y %b  %d %H:%M:%S"]:
            try:
                return datetime.strptime(ts_clean, fmt)
            except ValueError:
                continue

    # epoch seconds
    if ts_str.isdigit() and len(ts_str) == 10:
        try:
            return datetime.fromtimestamp(int(ts_str))
        except (OSError, OverflowError):
            pass

    # dateutil fallback
    try:
        from dateutil import parser as du_parser
        return du_parser.parse(ts_str, fuzzy=False)
    except Exception:
        pass

    return None


class GenericParser(BaseParser):
    name = "generic"
    supported_extensions = [".log", ".txt", ".out", ".err"]

    def probe(self, sample_lines: list[str]) -> float:
        return 0.1  # lowest priority fallback

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        entry = LogEntry()

        # Try to find a timestamp
        for pattern in _TS_PATTERNS:
            m = pattern.search(line)
            if m:
                ts = _parse_timestamp(m.group(1))
                if ts:
                    entry.timestamp = ts
                    break

        # Try to find log level
        lm = _LEVEL_RE.search(line)
        if lm:
            entry.level = lm.group(1).upper()

        # Message is everything after timestamp and level, or the whole line
        msg = line
        if entry.timestamp:
            ts_m = None
            for pattern in _TS_PATTERNS:
                ts_m = pattern.search(line)
                if ts_m:
                    break
            if ts_m:
                msg = line[ts_m.end():].strip(" |-:")
        if lm:
            lm2 = _LEVEL_RE.search(msg)
            if lm2:
                msg = msg[lm2.end():].strip(" |-:")

        entry.message = msg or line
        return entry
