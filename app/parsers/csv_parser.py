from __future__ import annotations
import csv
import io
from typing import Optional

from app.core.models import LogEntry
from app.parsers.base_parser import BaseParser
from app.parsers.generic_parser import _parse_timestamp

_TS_KEYS = {"timestamp", "time", "date", "datetime", "ts", "@timestamp"}
_LVL_KEYS = {"level", "severity", "loglevel", "log_level", "lvl"}
_MSG_KEYS = {"message", "msg", "log", "text", "body"}
_HOST_KEYS = {"hostname", "host", "server"}
_PID_KEYS = {"pid", "process_id"}


class CsvParser(BaseParser):
    name = "csv"
    supported_extensions = [".csv", ".tsv"]
    _headers: list[str] = []
    _delimiter: str = ","

    def probe(self, sample_lines: list[str]) -> float:
        non_empty = [l for l in sample_lines[:10] if l.strip()]
        if not non_empty:
            return 0.0
        try:
            joined = "\n".join(non_empty)
            dialect = csv.Sniffer().sniff(joined, delimiters=",;\t|")
            self._delimiter = dialect.delimiter
            # Require at least 2 columns in the majority of lines
            col_counts = [len(line.split(dialect.delimiter)) for line in non_empty]
            avg_cols = sum(col_counts) / len(col_counts)
            if avg_cols < 2.0:
                return 0.0
            return 0.7
        except csv.Error:
            return 0.0

    def parse_lines(self, lines: list[str], source_file: str) -> list[LogEntry]:
        if not lines:
            return []

        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=self._delimiter)
        entries: list[LogEntry] = []

        for row in reader:
            if not row:
                continue
            entry = LogEntry()
            keys_lower = {k.lower().strip(): v for k, v in row.items() if k}

            ts_val = next((keys_lower[k] for k in _TS_KEYS if k in keys_lower), None)
            if ts_val:
                entry.timestamp = _parse_timestamp(ts_val)

            lvl_val = next((keys_lower[k] for k in _LVL_KEYS if k in keys_lower), None)
            entry.level = (lvl_val or "").upper()

            msg_val = next((keys_lower[k] for k in _MSG_KEYS if k in keys_lower), None)
            entry.message = msg_val or str(dict(row))

            host_val = next((keys_lower[k] for k in _HOST_KEYS if k in keys_lower), None)
            entry.hostname = host_val or None

            pid_val = next((keys_lower[k] for k in _PID_KEYS if k in keys_lower), None)
            if pid_val:
                try:
                    entry.pid = int(pid_val)
                except ValueError:
                    pass

            entry.extra_fields = dict(row)
            entry.id = self._next_id()
            entry.source_file = source_file
            entry.raw_line = ",".join(str(v) for v in row.values())

            from app.parsers.base_parser import FieldExtractor
            FieldExtractor.enrich(entry)
            entries.append(entry)

        return entries

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        return None  # handled in parse_lines override
