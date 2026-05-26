from __future__ import annotations
import re
from typing import Optional

from app.core.models import LogEntry
from app.parsers.base_parser import BaseParser
from app.parsers.generic_parser import _parse_timestamp

# RFC 5424: <priority>version timestamp hostname app-name procid msgid structured-data msg
_RFC5424 = re.compile(
    r"^<(\d+)>(\d+)\s+"
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?|-)\s+"
    r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+"
    r"(?:\[.*?\]|-)\s*(.*)?$"
)

# RFC 3164: <priority>Mon dd HH:MM:SS hostname tag[pid]: msg
_RFC3164 = re.compile(
    r"^<(\d+)>(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\S+?)(?:\[(\d+)\])?:\s*(.*)"
)

# Plain syslog without priority: Mon dd HH:MM:SS hostname tag[pid]: msg
_PLAIN = re.compile(
    r"^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\S+?)(?:\[(\d+)\])?:\s*(.*)"
)

_FACILITY_NAMES = [
    "kern", "user", "mail", "daemon", "auth", "syslog", "lpr", "news",
    "uucp", "cron", "authpriv", "ftp",
]
_SEVERITY_NAMES = ["EMERG", "ALERT", "CRITICAL", "ERROR", "WARN", "NOTICE", "INFO", "DEBUG"]


def _priority_to_level(pri: int) -> str:
    severity = pri % 8
    return _SEVERITY_NAMES[severity] if severity < len(_SEVERITY_NAMES) else "INFO"


class SyslogParser(BaseParser):
    name = "syslog"
    supported_extensions = [".log", ".syslog"]

    def probe(self, sample_lines: list[str]) -> float:
        hits = sum(
            1 for l in sample_lines[:20]
            if l.strip() and (
                _RFC5424.match(l.strip()) or
                _RFC3164.match(l.strip()) or
                _PLAIN.match(l.strip())
            )
        )
        total = len([l for l in sample_lines[:20] if l.strip()])
        return min(0.95, hits / max(total, 1))

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        entry = LogEntry()

        m = _RFC5424.match(line)
        if m:
            pri = int(m.group(1))
            entry.level = _priority_to_level(pri)
            ts_str = m.group(3)
            if ts_str != "-":
                entry.timestamp = _parse_timestamp(ts_str)
            entry.hostname = m.group(4) if m.group(4) != "-" else None
            pid_str = m.group(6)
            if pid_str != "-":
                try:
                    entry.pid = int(pid_str)
                except ValueError:
                    entry.tid = pid_str
            entry.message = m.group(8) or ""
            return entry

        m = _RFC3164.match(line)
        if m:
            pri = int(m.group(1))
            entry.level = _priority_to_level(pri)
            entry.timestamp = _parse_timestamp(m.group(2))
            entry.hostname = m.group(3)
            if m.group(5):
                try:
                    entry.pid = int(m.group(5))
                except ValueError:
                    pass
            entry.message = m.group(6)
            return entry

        m = _PLAIN.match(line)
        if m:
            entry.timestamp = _parse_timestamp(m.group(1))
            entry.hostname = m.group(2)
            if m.group(4):
                try:
                    entry.pid = int(m.group(4))
                except ValueError:
                    pass
            entry.message = m.group(5)
            entry.level = "INFO"
            return entry

        return None
