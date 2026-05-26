from __future__ import annotations
import re
from typing import Optional

from app.core.models import LogEntry, FilterState
from app.search.indexer import LogIndex


class SearchEngine:
    def __init__(self, index: LogIndex) -> None:
        self._index = index

    def get_page(self, offset: int, limit: int, filter_state: Optional[FilterState] = None) -> list[LogEntry]:
        entries = self._index.get_page(offset, limit, filter_state)

        # Regex post-filter (SQLite can't run Python regex)
        if filter_state and filter_state.regex_mode and filter_state.search_text:
            entries = self._regex_filter(entries, filter_state)

        return entries

    def count(self, filter_state: Optional[FilterState] = None) -> int:
        if filter_state and filter_state.regex_mode and filter_state.search_text:
            # For regex we can't get an exact count cheaply; return estimate
            return self._index.count_filtered(filter_state)
        return self._index.count_filtered(filter_state)

    def _regex_filter(self, entries: list[LogEntry], f: FilterState) -> list[LogEntry]:
        flags = 0 if f.case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(f.search_text, flags)
        except re.error:
            return entries
        return [
            e for e in entries
            if pattern.search(e.message) or pattern.search(e.raw_line)
        ]

    def highlight_positions(self, text: str, filter_state: FilterState) -> list[tuple[int, int]]:
        """Return (start, end) positions of matches in text."""
        if not filter_state.search_text:
            return []
        try:
            if filter_state.regex_mode:
                flags = 0 if filter_state.case_sensitive else re.IGNORECASE
                pattern = re.compile(filter_state.search_text, flags)
            else:
                escaped = re.escape(filter_state.search_text)
                flags = 0 if filter_state.case_sensitive else re.IGNORECASE
                pattern = re.compile(escaped, flags)
            return [(m.start(), m.end()) for m in pattern.finditer(text)]
        except re.error:
            return []
