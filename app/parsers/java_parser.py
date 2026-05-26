from __future__ import annotations
import re
from typing import Optional

from app.core.models import LogEntry
from app.parsers.base_parser import BaseParser
from app.parsers.generic_parser import _parse_timestamp

# Log4j / Logback / Spring Boot pattern:
# 2024-01-15 10:30:45.123  INFO 12345 --- [main] com.example.App  : Starting application
_SPRING = re.compile(
    r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]\d+)\s+"
    r"(TRACE|DEBUG|INFO|WARN|ERROR|FATAL)\s+"
    r"(\d+)\s+---\s+\[([^\]]+)\]\s+"
    r"(\S+)\s*:\s+(.*)"
)

# Generic Log4j: 2024-01-15 10:30:45,123 [main] ERROR com.example.App - Message
_LOG4J = re.compile(
    r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]\d*)\s+"
    r"(?:\[([^\]]+)\]\s+)?"
    r"(TRACE|DEBUG|INFO|WARN|ERROR|FATAL|SEVERE)\s+"
    r"(?:(\S+)\s+[-–]\s+)?(.*)"
)

# Logback: 10:30:45.123 [main] INFO  com.example.App - Message
_LOGBACK = re.compile(
    r"^(\d{2}:\d{2}:\d{2}\.\d+)\s+\[([^\]]+)\]\s+"
    r"(TRACE|DEBUG|INFO|WARN|ERROR|FATAL)\s+"
    r"(\S+)\s+[-–]\s+(.*)"
)

# Java exception continuation lines
_EXCEPTION = re.compile(r"^\s+(at\s+\S+|\.\.\.\s+\d+\s+more|Caused by:)")


class JavaParser(BaseParser):
    name = "java"
    supported_extensions = [".log", ".out"]

    def probe(self, sample_lines: list[str]) -> float:
        hits = sum(
            1 for l in sample_lines[:30]
            if _SPRING.match(l.strip()) or _LOG4J.match(l.strip()) or _LOGBACK.match(l.strip())
        )
        total = len([l for l in sample_lines[:30] if l.strip()])
        return min(0.95, hits / max(total, 1))

    def parse_lines(self, lines: list[str], source_file: str) -> list[LogEntry]:
        """Override to handle multiline stack traces."""
        entries: list[LogEntry] = []
        current: Optional[LogEntry] = None

        for line in lines:
            if not line.strip():
                if current:
                    entries.append(current)
                    current = None
                continue

            if _EXCEPTION.match(line) and current:
                current.message += "\n" + line
                current.raw_line += "\n" + line
                continue

            if current:
                entries.append(current)

            entry = self._parse_line(line, source_file)
            if entry:
                entry.id = self._next_id()
                entry.source_file = source_file
                entry.raw_line = line
                if entry.level:
                    entry.level = entry.level.upper()
                from app.parsers.base_parser import FieldExtractor
                FieldExtractor.enrich(entry)
                current = entry
            else:
                current = LogEntry(
                    id=self._next_id(),
                    source_file=source_file,
                    raw_line=line,
                    message=line,
                )

        if current:
            entries.append(current)

        return entries

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        entry = LogEntry()

        m = _SPRING.match(line)
        if m:
            entry.timestamp = _parse_timestamp(m.group(1))
            entry.level = m.group(2)
            try:
                entry.pid = int(m.group(3))
            except ValueError:
                pass
            entry.tid = m.group(4)
            entry.extra_fields["logger"] = m.group(5)
            entry.message = m.group(6)
            return entry

        m = _LOG4J.match(line)
        if m:
            entry.timestamp = _parse_timestamp(m.group(1))
            entry.tid = m.group(2)
            entry.level = m.group(3)
            if m.group(4):
                entry.extra_fields["logger"] = m.group(4)
            entry.message = m.group(5)
            return entry

        m = _LOGBACK.match(line)
        if m:
            entry.timestamp = _parse_timestamp(m.group(1))
            entry.tid = m.group(2)
            entry.level = m.group(3)
            entry.extra_fields["logger"] = m.group(4)
            entry.message = m.group(5)
            return entry

        return None
