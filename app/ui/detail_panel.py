from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextEdit, QLabel, QFormLayout, QFrame, QScrollArea,
    QPushButton, QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor

from app.core.models import LogEntry


class DetailPanel(QWidget):
    correlate_requested = Signal(str)   # correlation_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(0)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        layout.addWidget(self._tabs)

        # Tab 1: Fields
        self._fields_widget = QScrollArea()
        self._fields_widget.setWidgetResizable(True)
        self._fields_widget.setFrameShape(QFrame.Shape.NoFrame)
        self._fields_container = QWidget()
        self._fields_layout = QFormLayout(self._fields_container)
        self._fields_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._fields_layout.setHorizontalSpacing(12)
        self._fields_widget.setWidget(self._fields_container)
        self._tabs.addTab(self._fields_widget, "Fields")

        # Tab 2: Raw line
        self._raw_edit = QTextEdit()
        self._raw_edit.setReadOnly(True)
        mono = QFont("Consolas", 9)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._raw_edit.setFont(mono)
        self._tabs.addTab(self._raw_edit, "Raw Line")

        # Tab 3: Extra fields
        self._extra_edit = QTextEdit()
        self._extra_edit.setReadOnly(True)
        self._extra_edit.setFont(mono)
        self._tabs.addTab(self._extra_edit, "Extra")

    def show_entry(self, entry: LogEntry) -> None:
        # Clear
        while self._fields_layout.rowCount():
            self._fields_layout.removeRow(0)

        def add_row(label: str, value: str) -> None:
            if value:
                lbl = QLabel(f"{label}:")
                lbl.setStyleSheet("color: #888; font-size: 11px;")
                val = QLabel(value)
                val.setWordWrap(True)
                val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self._fields_layout.addRow(lbl, val)

        from datetime import datetime
        ts = ""
        if entry.timestamp:
            if isinstance(entry.timestamp, datetime):
                ts = entry.timestamp.isoformat(sep=" ", timespec="milliseconds")
            else:
                ts = str(entry.timestamp)

        add_row("Timestamp", ts)
        add_row("Level", entry.level)
        add_row("Source", entry.source_file)
        add_row("Hostname", entry.hostname or "")
        add_row("PID", str(entry.pid) if entry.pid else "")
        add_row("TID", entry.tid or "")
        add_row("User", entry.user or "")
        add_row("Correlation ID", entry.correlation_id or "")
        add_row("Request ID", entry.request_id or "")
        add_row("Transaction ID", entry.transaction_id or "")
        add_row("Session ID", entry.session_id or "")
        add_row("Error Code", entry.error_code or "")
        add_row("IP Addresses", ", ".join(entry.ip_addresses))
        add_row("URLs", "\n".join(entry.urls))
        add_row("File Paths", "\n".join(entry.file_paths))
        add_row("Message", entry.message)

        # Correlate button
        if entry.correlation_id:
            btn = QPushButton(f"Correlate: {entry.correlation_id[:16]}…")
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda: self.correlate_requested.emit(entry.correlation_id))
            self._fields_layout.addRow("", btn)

        self._raw_edit.setPlainText(entry.raw_line)

        extra_text = ""
        if entry.extra_fields:
            import json
            extra_text = json.dumps(
                {k: v for k, v in entry.extra_fields.items() if not k.startswith("_")},
                indent=2, ensure_ascii=False,
            )
        self._extra_edit.setPlainText(extra_text)
