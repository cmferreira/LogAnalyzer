from __future__ import annotations
from datetime import timedelta
from typing import Optional

from app.core.models import LogEntry, CorrelationGroup
from app.search.indexer import LogIndex


class Correlator:
    def __init__(self, index: LogIndex) -> None:
        self._index = index

    def correlate_by_id(self, field: str = "correlation_id") -> list[CorrelationGroup]:
        """Group all entries by a shared ID field."""
        groups: dict[str, CorrelationGroup] = {}

        conn = self._index._conn
        rows = conn.execute(
            f"SELECT id, {field}, source_file, ts_epoch FROM entries "
            f"WHERE {field} IS NOT NULL AND {field} != '' "
            f"ORDER BY ts_epoch"
        ).fetchall()

        for row_id, field_val, src, ts_epoch in rows:
            if not field_val:
                continue
            if field_val not in groups:
                groups[field_val] = CorrelationGroup(
                    group_id=f"{field}:{field_val}",
                    criteria=field,
                    value=field_val,
                )
            g = groups[field_val]
            g.entry_ids.append(row_id)
            if src not in g.source_files:
                g.source_files.append(src)
            if ts_epoch:
                from datetime import datetime
                dt = datetime.fromtimestamp(ts_epoch)
                if g.first_seen is None or dt < g.first_seen:
                    g.first_seen = dt
                if g.last_seen is None or dt > g.last_seen:
                    g.last_seen = dt

        # Only return groups that span multiple files or have >= 2 entries
        return [g for g in groups.values() if len(g.entry_ids) >= 2]

    def correlate_by_proximity(
        self,
        pivot_entry: LogEntry,
        window_before_s: float = 300,
        window_after_s: float = 600,
    ) -> list[LogEntry]:
        """Return all entries within a time window around pivot_entry."""
        if pivot_entry.timestamp is None:
            return []

        ts = pivot_entry.timestamp.timestamp()
        conn = self._index._conn
        rows = conn.execute(
            "SELECT id, timestamp, level, source_file, message, raw_line,"
            " hostname, pid, tid, user_, correlation_id, request_id,"
            " transaction_id, session_id, error_code, ip_addresses,"
            " urls, file_paths, extra_fields, ts_epoch"
            " FROM entries"
            " WHERE ts_epoch >= ? AND ts_epoch <= ?"
            " ORDER BY ts_epoch",
            (ts - window_before_s, ts + window_after_s),
        ).fetchall()
        return [self._index._row_to_entry(r) for r in rows]

    def find_error_chains(self, window_s: float = 600) -> list[list[LogEntry]]:
        """Detect cascading WARN→ERROR→CRITICAL sequences within window_s."""
        conn = self._index._conn
        rows = conn.execute(
            "SELECT id, ts_epoch, level, source_file, message, raw_line,"
            " hostname, pid, tid, user_, correlation_id, request_id,"
            " transaction_id, session_id, error_code, ip_addresses,"
            " urls, file_paths, extra_fields"
            " FROM entries"
            " WHERE level IN ('WARN','WARNING','ERROR','ERR','CRITICAL','FATAL')"
            " ORDER BY ts_epoch"
        ).fetchall()

        chains: list[list[LogEntry]] = []
        current_chain: list[LogEntry] = []

        for r in rows:
            entry = self._index._row_to_entry(r)
            if not current_chain:
                current_chain = [entry]
                continue

            prev_ts = current_chain[-1].extra_fields.get("_ts_epoch", 0)
            cur_ts = r[1] or 0
            if abs(cur_ts - prev_ts) <= window_s:
                current_chain.append(entry)
            else:
                if len(current_chain) >= 3:
                    chains.append(current_chain)
                current_chain = [entry]
            entry.extra_fields["_ts_epoch"] = cur_ts

        if len(current_chain) >= 3:
            chains.append(current_chain)

        return chains

    def get_all_groups(self) -> list[CorrelationGroup]:
        groups: list[CorrelationGroup] = []
        for field in ["correlation_id", "request_id", "transaction_id", "session_id"]:
            groups.extend(self.correlate_by_id(field))
        return groups
