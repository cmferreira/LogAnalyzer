from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class LogEntry:
    id: int = 0
    timestamp: Optional[datetime] = None
    level: str = ""
    source_file: str = ""
    message: str = ""
    raw_line: str = ""
    hostname: Optional[str] = None
    pid: Optional[int] = None
    tid: Optional[str] = None
    user: Optional[str] = None
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None
    transaction_id: Optional[str] = None
    session_id: Optional[str] = None
    error_code: Optional[str] = None
    ip_addresses: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    extra_fields: dict = field(default_factory=dict)
    line_number: int = 0

    def normalized_level(self) -> str:
        mapping = {
            "TRACE": "TRACE", "DEBUG": "DEBUG",
            "INFO": "INFO", "INFORMATION": "INFO",
            "WARN": "WARN", "WARNING": "WARN",
            "ERROR": "ERROR", "ERR": "ERROR",
            "CRITICAL": "CRITICAL", "CRIT": "CRITICAL",
            "FATAL": "FATAL", "EMERG": "FATAL",
            "NOTICE": "INFO", "ALERT": "CRITICAL",
        }
        return mapping.get(self.level.upper(), self.level.upper() or "INFO")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
            "level": self.level,
            "source_file": self.source_file,
            "message": self.message,
            "raw_line": self.raw_line,
            "hostname": self.hostname or "",
            "pid": str(self.pid) if self.pid is not None else "",
            "tid": self.tid or "",
            "user": self.user or "",
            "correlation_id": self.correlation_id or "",
            "request_id": self.request_id or "",
            "transaction_id": self.transaction_id or "",
            "session_id": self.session_id or "",
            "error_code": self.error_code or "",
            "ip_addresses": ", ".join(self.ip_addresses),
            "urls": ", ".join(self.urls),
            "file_paths": ", ".join(self.file_paths),
        }


@dataclass
class LogFile:
    path: str
    format_name: str = "unknown"
    parser_name: str = "generic"
    entry_count: int = 0
    encoding: str = "utf-8"
    size_bytes: int = 0
    is_live: bool = False
    parse_errors: int = 0
    load_complete: bool = False


@dataclass
class CorrelationGroup:
    group_id: str
    criteria: str
    value: str
    entry_ids: list[int] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    @property
    def span_seconds(self) -> float:
        if self.first_seen and self.last_seen:
            return (self.last_seen - self.first_seen).total_seconds()
        return 0.0


@dataclass
class FilterState:
    search_text: str = ""
    regex_mode: bool = False
    case_sensitive: bool = False
    levels: list[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    sources: list[str] = field(default_factory=list)
    hostname: str = ""
    user: str = ""
    correlation_id: str = ""
    pid: str = ""
    exclude_expressions: list[str] = field(default_factory=list)
    errors_only: bool = False

    def is_empty(self) -> bool:
        return (
            not self.search_text
            and not self.levels
            and self.start_time is None
            and self.end_time is None
            and not self.sources
            and not self.hostname
            and not self.user
            and not self.correlation_id
            and not self.pid
            and not self.exclude_expressions
            and not self.errors_only
        )
