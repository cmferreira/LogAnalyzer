from __future__ import annotations
import json
import sqlite3
import threading
from typing import Optional

from app.core.models import LogEntry, FilterState


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY,
    timestamp   TEXT,
    ts_epoch    REAL,
    level       TEXT,
    source_file TEXT,
    message     TEXT,
    raw_line    TEXT,
    hostname    TEXT,
    pid         INTEGER,
    tid         TEXT,
    user_       TEXT,
    correlation_id TEXT,
    request_id  TEXT,
    transaction_id TEXT,
    session_id  TEXT,
    error_code  TEXT,
    ip_addresses TEXT,
    urls        TEXT,
    file_paths  TEXT,
    extra_fields TEXT
)
"""

_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    message,
    raw_line,
    hostname,
    user_,
    correlation_id,
    content='entries',
    content_rowid='id'
)
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_level ON entries(level)",
    "CREATE INDEX IF NOT EXISTS idx_ts ON entries(ts_epoch)",
    "CREATE INDEX IF NOT EXISTS idx_source ON entries(source_file)",
    "CREATE INDEX IF NOT EXISTS idx_hostname ON entries(hostname)",
    "CREATE INDEX IF NOT EXISTS idx_corr ON entries(correlation_id)",
    "CREATE INDEX IF NOT EXISTS idx_pid ON entries(pid)",
]

_INSERT = """
INSERT INTO entries
  (id, timestamp, ts_epoch, level, source_file, message, raw_line,
   hostname, pid, tid, user_, correlation_id, request_id, transaction_id,
   session_id, error_code, ip_addresses, urls, file_paths, extra_fields)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

_INSERT_FTS = """
INSERT INTO entries_fts(rowid, message, raw_line, hostname, user_, correlation_id)
VALUES (?,?,?,?,?,?)
"""


class LogIndex:
    """Thread-safe SQLite-backed log index with FTS5 search."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._bulk_loading = False
        self._conn = self._make_connection()
        self._init_schema()

    def _make_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-32000")  # 32 MB
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            c = self._conn
            c.execute(_CREATE_TABLE)
            c.execute(_CREATE_FTS)
            for idx in _CREATE_INDEXES:
                c.execute(idx)
            c.commit()

    def begin_bulk_load(self) -> None:
        with self._lock:
            self._bulk_loading = True
            self._conn.execute("PRAGMA synchronous=OFF")
            self._conn.execute("PRAGMA journal_mode=MEMORY")

    def end_bulk_load(self) -> None:
        with self._lock:
            self._bulk_loading = False
            try:
                self._conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
                self._conn.commit()
            except Exception:
                pass
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA journal_mode=WAL")

    def insert_batch(self, entries: list[LogEntry]) -> None:
        rows = []
        fts_rows = []
        bulk = self._bulk_loading
        for e in entries:
            try:
                ts_epoch = e.timestamp.timestamp() if e.timestamp else None
            except (OSError, OverflowError, ValueError):
                ts_epoch = None
            ts_str = e.timestamp.isoformat() if e.timestamp else None
            rows.append((
                e.id, ts_str, ts_epoch, e.level, e.source_file,
                e.message, e.raw_line, e.hostname, e.pid, e.tid,
                e.user, e.correlation_id, e.request_id, e.transaction_id,
                e.session_id, e.error_code,
                ", ".join(e.ip_addresses), ", ".join(e.urls),
                ", ".join(e.file_paths),
                json.dumps(e.extra_fields) if e.extra_fields else "",
            ))
            if not bulk:
                fts_rows.append((
                    e.id, e.message or "", e.raw_line or "",
                    e.hostname or "", e.user or "", e.correlation_id or "",
                ))

        with self._lock:
            self._conn.executemany(_INSERT, rows)
            if fts_rows:
                self._conn.executemany(_INSERT_FTS, fts_rows)
            self._conn.commit()

    def total_count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()
            return row[0] if row else 0

    def get_page(self, offset: int, limit: int, filter_state: Optional[FilterState] = None) -> list[LogEntry]:
        sql, params = self._build_query(filter_state, offset, limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def count_filtered(self, filter_state: Optional[FilterState]) -> int:
        if filter_state is None or filter_state.is_empty():
            return self.total_count()
        sql, params = self._build_count_query(filter_state)
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return row[0] if row else 0

    def _build_query(
        self, f: Optional[FilterState], offset: int, limit: int
    ) -> tuple[str, list]:
        clauses, params = self._filter_clauses(f)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f"""
            SELECT id, timestamp, level, source_file, message, raw_line,
                   hostname, pid, tid, user_, correlation_id, request_id,
                   transaction_id, session_id, error_code, ip_addresses,
                   urls, file_paths, extra_fields, ts_epoch
            FROM entries
            {where}
            ORDER BY ts_epoch ASC NULLS LAST, id ASC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        return sql, params

    def _build_count_query(self, f: Optional[FilterState]) -> tuple[str, list]:
        clauses, params = self._filter_clauses(f)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        return f"SELECT COUNT(*) FROM entries {where}", params

    def _filter_clauses(self, f: Optional[FilterState]) -> tuple[list[str], list]:
        if not f:
            return [], []
        clauses: list[str] = []
        params: list = []

        if f.errors_only:
            clauses.append("level IN ('ERROR','ERR','CRITICAL','FATAL')")

        if f.levels:
            placeholders = ",".join("?" * len(f.levels))
            clauses.append(f"level IN ({placeholders})")
            params.extend([l.upper() for l in f.levels])

        if f.start_time:
            clauses.append("ts_epoch >= ?")
            params.append(f.start_time.timestamp())

        if f.end_time:
            clauses.append("ts_epoch <= ?")
            params.append(f.end_time.timestamp())

        if f.sources:
            placeholders = ",".join("?" * len(f.sources))
            clauses.append(f"source_file IN ({placeholders})")
            params.extend(f.sources)

        if f.hostname:
            clauses.append("hostname LIKE ?")
            params.append(f"%{f.hostname}%")

        if f.user:
            clauses.append("user_ LIKE ?")
            params.append(f"%{f.user}%")

        if f.correlation_id:
            clauses.append("correlation_id = ?")
            params.append(f.correlation_id)

        if f.pid:
            try:
                clauses.append("pid = ?")
                params.append(int(f.pid))
            except ValueError:
                pass

        if f.search_text:
            if f.regex_mode:
                # Regex: Python-side filter; use FTS as pre-filter
                pass
            else:
                if f.case_sensitive:
                    clauses.append("(message LIKE ? OR raw_line LIKE ?)")
                    params.extend([f"%{f.search_text}%", f"%{f.search_text}%"])
                else:
                    clauses.append("(LOWER(message) LIKE ? OR LOWER(raw_line) LIKE ?)")
                    t = f.search_text.lower()
                    params.extend([f"%{t}%", f"%{t}%"])

        for excl in f.exclude_expressions:
            clauses.append("message NOT LIKE ? AND raw_line NOT LIKE ?")
            params.extend([f"%{excl}%", f"%{excl}%"])

        return clauses, params

    def _row_to_entry(self, r) -> LogEntry:
        extra = {}
        if r[18]:
            try:
                extra = json.loads(r[18])
            except Exception:
                pass
        return LogEntry(
            id=r[0],
            timestamp=r[1],  # ISO string; display code parses on demand
            level=r[2] or "",
            source_file=r[3] or "",
            message=r[4] or "",
            raw_line=r[5] or "",
            hostname=r[6],
            pid=r[7],
            tid=r[8],
            user=r[9],
            correlation_id=r[10],
            request_id=r[11],
            transaction_id=r[12],
            session_id=r[13],
            error_code=r[14],
            ip_addresses=[x.strip() for x in (r[15] or "").split(",") if x.strip()],
            urls=[x.strip() for x in (r[16] or "").split(",") if x.strip()],
            file_paths=[x.strip() for x in (r[17] or "").split(",") if x.strip()],
            extra_fields=extra,
        )

    def get_distinct_sources(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT source_file FROM entries ORDER BY source_file"
            ).fetchall()
        return [r[0] for r in rows if r[0]]

    def get_distinct_levels(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT level FROM entries ORDER BY level"
            ).fetchall()
        return [r[0] for r in rows if r[0]]

    def get_entries_by_correlation_id(self, corr_id: str) -> list[LogEntry]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, timestamp, level, source_file, message, raw_line,"
                " hostname, pid, tid, user_, correlation_id, request_id,"
                " transaction_id, session_id, error_code, ip_addresses,"
                " urls, file_paths, extra_fields, ts_epoch"
                " FROM entries WHERE correlation_id = ? ORDER BY ts_epoch",
                (corr_id,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM entries")
            self._conn.execute("DELETE FROM entries_fts")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
