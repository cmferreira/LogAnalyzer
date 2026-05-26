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
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("Open Files")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._context_menu)
        self._tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._tree)

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
            name = os.path.basename(path)
            count_str = f" ({lf.entry_count:,})" if lf.entry_count else ""
            live_str = " ▶" if lf.is_live else ""
            item = QTreeWidgetItem([f"{name}{count_str}{live_str}"])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item.setToolTip(0, path)
            # sub-items
            fmt_item = QTreeWidgetItem([f"Format: {lf.format_name}"])
            enc_item = QTreeWidgetItem([f"Encoding: {lf.encoding}"])
            size_kb = lf.size_bytes / 1024
            size_item = QTreeWidgetItem([f"Size: {size_kb:.1f} KB"])
            item.addChildren([fmt_item, enc_item, size_item])
            self._tree.addTopLevelItem(item)

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
