from __future__ import annotations
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QMenu, QPushButton, QHBoxLayout,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon, QAction

from app.core.models import LogFile


class FilePanel(QWidget):
    file_selected = Signal(str)         # path
    file_close_requested = Signal(str)  # path
    file_live_requested = Signal(str)   # path

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(260)
        self._files: dict[str, LogFile] = {}
        self._progress: dict[str, int] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(32)
        title_bar.setStyleSheet(
            "background-color: #252526; border-bottom: 1px solid #3c3c3c;"
        )
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(10, 0, 8, 0)
        title_bar_layout.setSpacing(0)

        title = QLabel("OPEN FILES")
        title.setStyleSheet(
            "color: #858585; font-size: 11px; font-weight: 700; "
            "letter-spacing: 1px; background: transparent; border: none;"
        )
        title_bar_layout.addWidget(title)
        title_bar_layout.addStretch()
        layout.addWidget(title_bar)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._context_menu)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.setIndentation(12)
        self._tree.setStyleSheet(
            "QTreeWidget { background-color: #252526; border: none; }"
            "QTreeWidget::item { padding: 2px 4px; }"
            "QTreeWidget::item:hover { background-color: #2a2d2e; }"
            "QTreeWidget::item:selected { background-color: #094771; }"
        )
        layout.addWidget(self._tree)

    def set_loading(self, path: str, pct: int) -> None:
        self._progress[path] = pct
        self._update_item_label(path)

    def clear_loading(self, path: str) -> None:
        self._progress.pop(path, None)
        self._update_item_label(path)

    def _item_label(self, lf: LogFile, path: str) -> str:
        name = os.path.basename(path)
        pct = self._progress.get(path)
        count_str = f" ({lf.entry_count:,})" if lf.entry_count else ""
        live_str = "  ▶" if lf.is_live else ""
        pct_str = f"  [{pct}%]" if pct is not None else ""
        return f"{name}{count_str}{live_str}{pct_str}"

    def _update_item_label(self, path: str) -> None:
        lf = self._files.get(path)
        if not lf:
            return
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == path:
                item.setText(0, self._item_label(lf, path))
                return

    def add_file(self, log_file: LogFile) -> None:
        self._files[log_file.path] = log_file
        self._refresh_tree()

    def update_file(self, log_file: LogFile) -> None:
        self._files[log_file.path] = log_file
        self._refresh_tree()

    def remove_file(self, path: str) -> None:
        self._files.pop(path, None)
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        self._tree.clear()
        for path, lf in self._files.items():
            item = QTreeWidgetItem([self._item_label(lf, path)])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item.setToolTip(0, path)
            size_kb = lf.size_bytes / 1024
            size_str = f"{size_kb / 1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"
            item.addChildren([
                QTreeWidgetItem([f"Format: {lf.format_name}"]),
                QTreeWidgetItem([f"Encoding: {lf.encoding}"]),
                QTreeWidgetItem([f"Size: {size_str}"]),
            ])
            self._tree.addTopLevelItem(item)
            item.setExpanded(True)

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.file_selected.emit(path)

    def _context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return

        menu = QMenu(self)
        close_action = QAction("Close File", self)
        close_action.triggered.connect(lambda: self.file_close_requested.emit(path))
        menu.addAction(close_action)

        live = self._files.get(path)
        if live and not live.is_live:
            live_action = QAction("Start Live Monitor", self)
            live_action.triggered.connect(lambda: self.file_live_requested.emit(path))
            menu.addAction(live_action)

        menu.exec(self._tree.mapToGlobal(pos))
