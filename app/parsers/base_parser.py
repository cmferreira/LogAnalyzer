from __future__ import annotations
import re
from abc import ABC, abstractmethod
from typing import Optional

from app.core.models import LogEntry
from app.core.interfaces import IParser


# Common regex patterns reused across parsers
RE_UUID = re.compile(
    r"\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b"
)
RE_IP = re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3})\b")
RE_URL = re.compile(r"(https?://[^\s\"'>]+)")
RE_FILE_PATH_WIN = re.compile(r"([A-Za-z]:\\[\w\\./_-]+)")
RE_FILE_PATH_UNIX = re.compile(r"(/[\w./_ -]+\.\w+)")
RE_PID = re.compile(r"(?:pid|PID)[=:\s]+(\d+)")
RE_TID = re.compile(r"(?:tid|TID|thread)[=:\s]+([\w-]+)")
RE_ERROR_CODE = re.compile(r"\b(E\d{4,}|0x[0-9A-Fa-f]{4,}|errno\s*\d+)\b")
RE_CORR_ID = re.compile(
    r"(?:correlation[_-]?id|corr[_-]?id|correlationId)[=:\s\"']+([0-9a-zA-Z_\-]+)",
    re.IGNORECASE,
)
RE_REQUEST_ID = re.compile(
    r"(?:request[_-]?id|req[_-]?id|requestId|X-Request-ID)[=:\s\"']+([0-9a-zA-Z_\-]+)",
    re.IGNORECASE,
)
RE_TRANSACTION_ID = re.compile(
    r"(?:transaction[_-]?id|txn[_-]?id|tx[_-]?id|transactionId)[=:\s\"']+([0-9a-zA-Z_\-]+)",
    re.IGNORECASE,
)
RE_SESSION_ID = re.compile(
    r"(?:session[_-]?id|sess[_-]?id|sessionId)[=:\s\"']+([0-9a-zA-Z_\-]+)",
    re.IGNORECASE,
)
RE_USER = re.compile(
    r"(?:user|username|userid|user_id)[=:\s\"']+([a-zA-Z0-9_@.\-]+)",
    re.IGNORECASE,
)


class FieldExtractor:
    """Post-processes a LogEntry to enrich with extracted fields from raw_line."""

    @staticmethod
    def enrich(entry: LogEntry) -> LogEntry:
        text = entry.raw_line

        if not entry.correlation_id:
            m = RE_CORR_ID.search(text)
            if m:
                entry.correlation_id = m.group(1)

        if not entry.request_id:
            m = RE_REQUEST_ID.search(text)
            if m:
                entry.request_id = m.group(1)

        if not entry.transaction_id:
            m = RE_TRANSACTION_ID.search(text)
            if m:
                entry.transaction_id = m.group(1)

        if not entry.session_id:
            m = RE_SESSION_ID.search(text)
            if m:
                entry.session_id = m.group(1)

        if not entry.user:
            m = RE_USER.search(text)
            if m:
                entry.user = m.group(1)

        if not entry.pid:
            m = RE_PID.search(text)
            if m:
                try:
                    entry.pid = int(m.group(1))
                except ValueError:
                    pass

        if not entry.tid:
            m = RE_TID.search(text)
            if m:
                entry.tid = m.group(1)

        if not entry.error_code:
            m = RE_ERROR_CODE.search(text)
            if m:
                entry.error_code = m.group(1)

        if not entry.ip_addresses:
            entry.ip_addresses = RE_IP.findall(text)

        if not entry.urls:
            entry.urls = RE_URL.findall(text)

        if not entry.file_paths:
            win = RE_FILE_PATH_WIN.findall(text)
            unix = RE_FILE_PATH_UNIX.findall(text)
            entry.file_paths = win + unix

        # UUID-based fallback for correlation_id
        if not entry.correlation_id:
            uuids = RE_UUID.findall(text)
            if uuids:
                entry.correlation_id = uuids[0]

        return entry


class BaseParser(IParser, ABC):
    name: str = "base"
    supported_extensions: list[str] = []
    _id_counter: int = 0

    def _next_id(self) -> int:
        BaseParser._id_counter += 1
        return BaseParser._id_counter

    @classmethod
    def reset_counter(cls) -> None:
        cls._id_counter = 0

    def parse_lines(self, lines: list[str], source_file: str) -> list[LogEntry]:
        entries: list[LogEntry] = []
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                entry = self._parse_line(line, source_file)
                if entry:
                    entry.id = self._next_id()
                    entry.source_file = source_file
                    entry.raw_line = line
                    if entry.level:
                        entry.level = entry.level.upper()
                    FieldExtractor.enrich(entry)
                    entries.append(entry)
            except Exception:
                entry = LogEntry(
                    id=self._next_id(),
                    source_file=source_file,
                    raw_line=line,
                    message=line,
                    level="",
                )
                entries.append(entry)
        return entries

    @abstractmethod
    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        """Parse a single raw line; return None to skip."""
