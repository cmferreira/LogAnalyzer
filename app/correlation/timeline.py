from __future__ import annotations
from datetime import datetime
from typing import Optional

from app.core.models import LogEntry
from app.search.indexer import LogIndex


class UnifiedTimeline:
    """Builds a chronologically sorted unified view across all loaded files."""

    def __init__(self, index: LogIndex) -> None:
        self._index = index

    def get_range(self) -> tuple[Optional[datetime], Optional[datetime]]:
        conn = self._index._conn
        row = conn.execute(
            "SELECT MIN(ts_epoch), MAX(ts_epoch) FROM entries WHERE ts_epoch IS NOT NULL"
        ).fetchone()
        if not row or row[0] is None:
            return None, None
        return datetime.fromtimestamp(row[0]), datetime.fromtimestamp(row[1])

    def get_window(
        self,
        center: datetime,
        before_s: float = 300,
        after_s: float = 600,
        sources: list[str] | None = None,
    ) -> list[LogEntry]:
        ts = center.timestamp()
        conn = self._index._conn

        where = "WHERE ts_epoch >= ? AND ts_epoch <= ?"
        params: list = [ts - before_s, ts + after_s]

        if sources:
            placeholders = ",".join("?" * len(sources))
            where += f" AND source_file IN ({placeholders})"
            params.extend(sources)

        rows = conn.execute(
            f"SELECT id, timestamp, level, source_file, message, raw_line,"
            f" hostname, pid, tid, user_, correlation_id, request_id,"
            f" transaction_id, session_id, error_code, ip_addresses,"
            f" urls, file_paths, extra_fields, ts_epoch"
            f" FROM entries {where} ORDER BY ts_epoch",
            params,
        ).fetchall()
        return [self._index._row_to_entry(r) for r in rows]

    def get_level_distribution(self, bucket_count: int = 50) -> list[dict]:
        """Return time-bucketed level counts for a histogram view."""
        ts_min, ts_max = self.get_range()
        if ts_min is None or ts_max is None:
            return []

        span = (ts_max - ts_min).total_seconds()
        if span <= 0:
            return []

        bucket_size = span / bucket_count
        conn = self._index._conn
        rows = conn.execute(
            "SELECT ts_epoch, level FROM entries WHERE ts_epoch IS NOT NULL ORDER BY ts_epoch"
        ).fetchall()

        buckets: list[dict] = [
            {
                "start": ts_min.timestamp() + i * bucket_size,
                "INFO": 0, "WARN": 0, "ERROR": 0, "CRITICAL": 0,
                "DEBUG": 0, "TRACE": 0, "OTHER": 0,
            }
            for i in range(bucket_count)
        ]

        for ts_epoch, level in rows:
            if ts_epoch is None:
                continue
            idx = int((ts_epoch - ts_min.timestamp()) / bucket_size)
            idx = min(idx, bucket_count - 1)
            lvl = (level or "").upper()
            if lvl in ("INFO", "WARN", "WARNING", "ERROR", "ERR", "CRITICAL", "FATAL", "DEBUG", "TRACE"):
                normalized = {"WARNING": "WARN", "ERR": "ERROR", "FATAL": "CRITICAL"}.get(lvl, lvl)
                key = normalized if normalized in buckets[idx] else "OTHER"
            else:
                key = "OTHER"
            buckets[idx][key] += 1

        return buckets
