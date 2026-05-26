from __future__ import annotations
import os
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QSplitter, QTextEdit, QPushButton,
    QComboBox, QGroupBox, QScrollArea, QFrame,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QBrush, QFont

from app.core.models import LogEntry, CorrelationGroup


_SOURCE_COLORS = [
    "#1E88E5", "#43A047", "#E53935", "#8E24AA",
    "#FB8C00", "#00ACC1", "#6D4C41", "#546E7A",
]


class CorrelationView(QWidget):
    """Shows correlation groups and a unified timeline."""

    entry_selected = Signal(object)  # LogEntry

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source_colors: dict[str, str] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("Correlation & Timeline View")
        header.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left: correlation groups list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Correlation Groups"))
        self._groups_table = QTableWidget()
        self._groups_table.setColumnCount(4)
        self._groups_table.setHorizontalHeaderLabels(["Criteria", "Value", "Events", "Duration"])
        self._groups_table.setSelectionBehavior(self._groups_table.SelectionBehavior.SelectRows)
        self._groups_table.setEditTriggers(self._groups_table.EditTrigger.NoEditTriggers)
        self._groups_table.verticalHeader().setVisible(False)
        self._groups_table.itemSelectionChanged.connect(self._on_group_selected)
        left_layout.addWidget(self._groups_table)
        splitter.addWidget(left)

        # Right: timeline
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Timeline"))
        self._timeline_table = QTableWidget()
        self._timeline_table.setColumnCount(4)
        self._timeline_table.setHorizontalHeaderLabels(["Time", "Level", "Source", "Message"])
        self._timeline_table.setSelectionBehavior(self._timeline_table.SelectionBehavior.SelectRows)
        self._timeline_table.setEditTriggers(self._timeline_table.EditTrigger.NoEditTriggers)
        self._timeline_table.verticalHeader().setVisible(False)
        self._timeline_table.setColumnWidth(0, 160)
        self._timeline_table.setColumnWidth(1, 70)
        self._timeline_table.setColumnWidth(2, 140)
        self._timeline_table.horizontalHeader().setStretchLastSection(True)
        self._timeline_table.itemClicked.connect(self._on_timeline_click)
        right_layout.addWidget(self._timeline_table)
        splitter.addWidget(right)
        splitter.setSizes([300, 700])

        self._groups: list[CorrelationGroup] = []
        self._group_entries: dict[str, list[LogEntry]] = {}

    def load_groups(self, groups: list[CorrelationGroup]) -> None:
        self._groups = groups
        self._groups_table.setRowCount(len(groups))
        for row, g in enumerate(groups):
            self._groups_table.setItem(row, 0, QTableWidgetItem(g.criteria))
            val_item = QTableWidgetItem(g.value[:30])
            val_item.setToolTip(g.value)
            self._groups_table.setItem(row, 1, val_item)
            self._groups_table.setItem(row, 2, QTableWidgetItem(str(len(g.entry_ids))))
            span = f"{g.span_seconds:.1f}s" if g.span_seconds else ""
            self._groups_table.setItem(row, 3, QTableWidgetItem(span))

    def show_entries(self, entries: list[LogEntry]) -> None:
        sources = sorted({e.source_file for e in entries})
        for i, src in enumerate(sources):
            if src not in self._source_colors:
                self._source_colors[src] = _SOURCE_COLORS[len(self._source_colors) % len(_SOURCE_COLORS)]

        self._timeline_table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            ts = ""
            if e.timestamp:
                if isinstance(e.timestamp, datetime):
                    ts = e.timestamp.strftime("%H:%M:%S.%f")[:-3]
                else:
                    ts = str(e.timestamp)

            ts_item = QTableWidgetItem(ts)
            lvl_item = QTableWidgetItem(e.level)
            src_item = QTableWidgetItem(os.path.basename(e.source_file))
            msg_item = QTableWidgetItem(e.message[:200])

            src_color = self._source_colors.get(e.source_file, "#888888")
            src_item.setForeground(QBrush(QColor(src_color)))

            for item in (ts_item, lvl_item, src_item, msg_item):
                item.setData(Qt.ItemDataRole.UserRole, e)

            self._timeline_table.setItem(row, 0, ts_item)
            self._timeline_table.setItem(row, 1, lvl_item)
            self._timeline_table.setItem(row, 2, src_item)
            self._timeline_table.setItem(row, 3, msg_item)
            self._timeline_table.setRowHeight(row, 22)

    def _on_group_selected(self) -> None:
        rows = self._groups_table.selectedItems()
        if not rows:
            return
        row = self._groups_table.currentRow()
        if row < len(self._groups):
            g = self._groups[row]
            entries = self._group_entries.get(g.group_id, [])
            self.show_entries(entries)

    def _on_timeline_click(self, item: QTableWidgetItem) -> None:
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry:
            self.entry_selected.emit(entry)

    def register_group_entries(self, group_id: str, entries: list[LogEntry]) -> None:
        self._group_entries[group_id] = entries
