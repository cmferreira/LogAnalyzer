from __future__ import annotations
import json
from datetime import datetime
from typing import Optional

from app.core.models import LogEntry
from app.parsers.base_parser import BaseParser
from app.parsers.generic_parser import _parse_timestamp

_TS_KEYS = ["timestamp", "time", "@timestamp", "ts", "date", "datetime", "log_time"]
_LEVEL_KEYS = ["level", "severity", "log_level", "loglevel", "lvl", "priority"]
_MSG_KEYS = ["message", "msg", "log", "text", "body", "event"]
_HOST_KEYS = ["hostname", "host", "server", "node"]
_PID_KEYS = ["pid", "process_id", "processId"]
_TID_KEYS = ["tid", "thread_id", "threadId", "thread"]
_USER_KEYS = ["user", "username", "user_name", "userId", "user_id"]
_CORR_KEYS = ["correlation_id", "correlationId", "corr_id", "trace_id", "traceId"]
_REQ_KEYS = ["request_id", "requestId", "req_id", "x-request-id"]
_TXN_KEYS = ["transaction_id", "transactionId", "txn_id", "tx_id"]
_SESS_KEYS = ["session_id", "sessionId", "sess_id"]


def _find(d: dict, keys: list[str]):
    for k in keys:
        if k in d:
            return d[k]
    return None


class JsonParser(BaseParser):
    name = "json"
    supported_extensions = [".json", ".jsonl", ".ndjson"]

    def probe(self, sample_lines: list[str]) -> float:
        hits = 0
        for line in sample_lines[:20]:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    json.loads(line)
                    hits += 1
                except json.JSONDecodeError:
                    pass
        return min(1.0, hits / max(len([l for l in sample_lines[:20] if l.strip()]), 1))

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        line = line.strip()
        if not line or not line.startswith("{"):
            return None
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            return None

        if not isinstance(d, dict):
            return None

        entry = LogEntry()

        ts_val = _find(d, _TS_KEYS)
        if ts_val:
            if isinstance(ts_val, (int, float)):
                try:
                    entry.timestamp = datetime.fromtimestamp(ts_val)
                except (OSError, OverflowError):
                    pass
            elif isinstance(ts_val, str):
                entry.timestamp = _parse_timestamp(ts_val)

        level_val = _find(d, _LEVEL_KEYS)
        if level_val:
            entry.level = str(level_val).upper()

        msg_val = _find(d, _MSG_KEYS)
        entry.message = str(msg_val) if msg_val is not None else line

        entry.hostname = str(_find(d, _HOST_KEYS) or "") or None

        pid_val = _find(d, _PID_KEYS)
        if pid_val is not None:
            try:
                entry.pid = int(pid_val)
            except (ValueError, TypeError):
                pass

        tid_val = _find(d, _TID_KEYS)
        if tid_val is not None:
            entry.tid = str(tid_val)

        entry.user = str(_find(d, _USER_KEYS) or "") or None
        entry.correlation_id = str(_find(d, _CORR_KEYS) or "") or None
        entry.request_id = str(_find(d, _REQ_KEYS) or "") or None
        entry.transaction_id = str(_find(d, _TXN_KEYS) or "") or None
        entry.session_id = str(_find(d, _SESS_KEYS) or "") or None

        # Store unrecognised fields
        known = set(
            _TS_KEYS + _LEVEL_KEYS + _MSG_KEYS + _HOST_KEYS + _PID_KEYS +
            _TID_KEYS + _USER_KEYS + _CORR_KEYS + _REQ_KEYS + _TXN_KEYS + _SESS_KEYS
        )
        entry.extra_fields = {k: v for k, v in d.items() if k not in known}

        return entry
