from __future__ import annotations
import re
from typing import Optional

from app.core.models import LogEntry
from app.parsers.base_parser import BaseParser
from app.parsers.generic_parser import _parse_timestamp

# Apache Combined Log Format
_ACCESS = re.compile(
    r'^(\S+)\s+'           # host
    r'(\S+)\s+'            # ident
    r'(\S+)\s+'            # user
    r'\[([^\]]+)\]\s+'     # [timestamp]
    r'"([^"]*?)"\s+'       # "request"
    r'(\d{3})\s+'          # status
    r'(\S+)'               # bytes
    r'(?:\s+"([^"]*)"\s+"([^"]*)")?'  # referer user-agent
)

# Apache Error Log
_ERROR = re.compile(
    r'^\[([^\]]+)\]\s+'            # [timestamp]
    r'\[(?:(\w+):)?(\w+)\]\s+'     # [module:level]
    r'(?:\[pid\s+(\d+)(?::tid\s+(\d+))?\]\s+)?'  # [pid N:tid N]
    r'(?:\[client\s+([^\]]+)\]\s+)?'  # [client ip:port]
    r'(.*)'                         # message
)

_NGINX_ACCESS = re.compile(
    r'^(\S+)\s+-\s+(\S+)\s+\[([^\]]+)\]\s+"([^"]*?)"\s+(\d{3})\s+(\d+)'
    r'(?:\s+"([^"]*)"\s+"([^"]*)")?'
)

_NGINX_ERROR = re.compile(
    r'^(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+(\d+)#(\d+):\s+(.*)'
)

_HTTP_LEVEL = {
    "1": "INFO", "2": "INFO", "3": "WARN", "4": "WARN", "5": "ERROR",
}


class ApacheAccessParser(BaseParser):
    name = "apache_access"
    supported_extensions = [".log", ".access"]

    def probe(self, sample_lines: list[str]) -> float:
        hits = sum(1 for l in sample_lines[:20] if _ACCESS.match(l.strip()))
        total = len([l for l in sample_lines[:20] if l.strip()])
        return min(0.95, hits / max(total, 1))

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        m = _ACCESS.match(line)
        if not m:
            return None
        entry = LogEntry()
        entry.hostname = m.group(1)
        if m.group(3) != "-":
            entry.user = m.group(3)
        entry.timestamp = _parse_timestamp(m.group(4))
        status = m.group(6)
        entry.level = _HTTP_LEVEL.get(status[0], "INFO")
        entry.extra_fields["status"] = status
        entry.extra_fields["bytes"] = m.group(7)
        if m.group(8):
            entry.extra_fields["referer"] = m.group(8)
        if m.group(9):
            entry.extra_fields["user_agent"] = m.group(9)
        entry.message = m.group(5)
        return entry


class ApacheErrorParser(BaseParser):
    name = "apache_error"
    supported_extensions = [".log", ".error"]

    def probe(self, sample_lines: list[str]) -> float:
        hits = sum(1 for l in sample_lines[:20] if _ERROR.match(l.strip()))
        total = len([l for l in sample_lines[:20] if l.strip()])
        return min(0.9, hits / max(total, 1))

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        m = _ERROR.match(line)
        if not m:
            return None
        entry = LogEntry()
        entry.timestamp = _parse_timestamp(m.group(1))
        entry.level = (m.group(3) or "ERROR").upper()
        if m.group(4):
            try:
                entry.pid = int(m.group(4))
            except ValueError:
                pass
        if m.group(6):
            entry.ip_addresses = [m.group(6).split(":")[0]]
        entry.message = m.group(7)
        return entry


class NginxAccessParser(BaseParser):
    name = "nginx_access"
    supported_extensions = [".log", ".access"]

    def probe(self, sample_lines: list[str]) -> float:
        hits = sum(1 for l in sample_lines[:20] if _NGINX_ACCESS.match(l.strip()))
        total = len([l for l in sample_lines[:20] if l.strip()])
        return min(0.9, hits / max(total, 1))

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        m = _NGINX_ACCESS.match(line)
        if not m:
            return None
        entry = LogEntry()
        entry.hostname = m.group(1)
        if m.group(2) != "-":
            entry.user = m.group(2)
        entry.timestamp = _parse_timestamp(m.group(3))
        status = m.group(5)
        entry.level = _HTTP_LEVEL.get(status[0], "INFO")
        entry.extra_fields["status"] = status
        entry.extra_fields["bytes"] = m.group(6)
        entry.message = m.group(4)
        return entry


class NginxErrorParser(BaseParser):
    name = "nginx_error"
    supported_extensions = [".log", ".error"]

    def probe(self, sample_lines: list[str]) -> float:
        hits = sum(1 for l in sample_lines[:20] if _NGINX_ERROR.match(l.strip()))
        total = len([l for l in sample_lines[:20] if l.strip()])
        return min(0.9, hits / max(total, 1))

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        m = _NGINX_ERROR.match(line)
        if not m:
            return None
        entry = LogEntry()
        entry.timestamp = _parse_timestamp(m.group(1))
        entry.level = m.group(2).upper()
        try:
            entry.pid = int(m.group(3))
        except ValueError:
            pass
        entry.message = m.group(5)
        return entry
