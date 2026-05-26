from __future__ import annotations
from datetime import datetime
from functools import lru_cache
from typing import Optional, Any

from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
    Signal, QTimer,
)
from PySide6.QtGui import QColor, QFont, QBrush
from PySide6.QtWidgets import QTableView, QHeaderView, QAbstractItemView

from app.core.models import LogEntry, FilterState
from app.core.constants import LEVEL_COLORS_DARK, LEVEL_COLORS_LIGHT, PAGE_SIZE
from app.search.indexer import LogIndex
from app.search.search_engine import SearchEngine

_COLUMNS = [
    ("Timestamp", "timestamp"),
    ("Level", "level"),
    ("Source", "source_file"),
    ("Host", "hostname"),
    ("PID", "pid"),
    ("TID", "tid"),
    ("Corr ID", "correlation_id"),
    ("Message", "message"),
    ("Raw Line", "raw_line"),
]

_COL_WIDTHS = [160, 70, 150, 100, 55, 80, 140, 600, 0]


class LogTableModel(QAbstractTableModel):
    row_count_changed = Signal(int)

    def __init__(self, index: LogIndex, dark_mode: bool = True) -> None:
        super().__init__()
        self._index = index
        self._engine = SearchEngine(index)
        self._filter: Optional[FilterState] = None
        self._dark = dark_mode
        self._total = 0
        self._page_cache: dict[int, list[LogEntry]] = {}
        self._page_size = PAGE_SIZE

    def set_dark_mode(self, dark: bool) -> None:
        self._dark = dark
        self.layoutChanged.emit()

    def refresh(self) -> None:
        self._page_cache.clear()
        self._total = self._engine.count(self._filter)
        self.beginResetModel()
        self.endResetModel()
        self.row_count_changed.emit(self._total)

    def set_filter(self, f: Optional[FilterState]) -> None:
        self._filter = f
        self.refresh()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self._total

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        entry = self._get_entry(row)
        if entry is None:
            return None

        field = _COLUMNS[col][1]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(entry, field)

        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground(entry)

        if role == Qt.ItemDataRole.BackgroundRole:
            return self._background(entry, row)

        if role == Qt.ItemDataRole.UserRole:
            return entry

        if role == Qt.ItemDataRole.FontRole and field == "level":
            f = QFont()
            f.setBold(True)
            return f

        return None

    def _display(self, entry: LogEntry, field: str) -> str:
        val = getattr(entry, field, None)
        if val is None:
            return ""
        if field == "timestamp":
            if isinstance(val, datetime):
                return val.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            # Parse from raw ISO string stored in DB
            try:
                dt = datetime.fromisoformat(str(val))
                return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            except (ValueError, TypeError):
                return str(val)
        if field == "source_file":
            import os
            return os.path.basename(str(val))
        return str(val)

    def _foreground(self, entry: LogEntry) -> QBrush:
        colors = LEVEL_COLORS_DARK if self._dark else LEVEL_COLORS_LIGHT
        fg, _ = colors.get(entry.level.upper(), colors[""])
        return QBrush(QColor(fg))

    def _background(self, entry: LogEntry, row: int) -> QBrush:
        colors = LEVEL_COLORS_DARK if self._dark else LEVEL_COLORS_LIGHT
        _, bg = colors.get(entry.level.upper(), colors[""])
        c = QColor(bg)
        # Slight alternating tint for non-colored rows
        if entry.level.upper() in ("", "INFO", "DEBUG", "TRACE"):
            if row % 2 == 1:
                if self._dark:
                    c = QColor(28, 28, 28)
                else:
                    c = QColor(248, 248, 248)
        return QBrush(c)

    def _get_entry(self, row: int) -> Optional[LogEntry]:
        page = row // self._page_size
        page_row = row % self._page_size

        if page not in self._page_cache:
            # Evict oldest page if cache is full
            if len(self._page_cache) >= 10:
                oldest = next(iter(self._page_cache))
                del self._page_cache[oldest]
            offset = page * self._page_size
            self._page_cache[page] = self._engine.get_page(
                offset, self._page_size, self._filter
            )

        page_entries = self._page_cache.get(page, [])
        if page_row < len(page_entries):
            return page_entries[page_row]
        return None

    def get_entry(self, row: int) -> Optional[LogEntry]:
        return self._get_entry(row)

    def invalidate_cache(self) -> None:
        self._page_cache.clear()


class LogTableView(QTableView):
    entry_selected = Signal(object)  # LogEntry

    def __init__(self, model: LogTableModel, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self.setModel(model)
        self._setup_view()
        self.selectionModel().currentRowChanged.connect(self._on_row_changed)

    def _setup_view(self) -> None:
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(False)  # We handle it manually
        self.setWordWrap(False)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(22)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(
            len(_COLUMNS) - 2, QHeaderView.ResizeMode.Stretch
        )
        self.setColumnHidden(len(_COLUMNS) - 1, True)  # Hide raw line column by default

        for i, w in enumerate(_COL_WIDTHS[:-1]):
            if w > 0:
                self.setColumnWidth(i, w)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _on_row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        entry = self._model.get_entry(current.row())
        if entry:
            self.entry_selected.emit(entry)

    def scroll_to_bottom(self) -> None:
        self.scrollToBottom()

    def toggle_raw_column(self, show: bool) -> None:
        self.setColumnHidden(len(_COLUMNS) - 1, not show)
