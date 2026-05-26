from __future__ import annotations
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QListWidget, QListWidgetItem, QLabel,
    QDateTimeEdit, QLineEdit, QPushButton, QScrollArea,
    QFrame,
)
from PySide6.QtCore import Signal, Qt, QDateTime

from app.core.models import FilterState
from app.core.constants import LEVELS_ORDERED


class FilterPanel(QWidget):
    filter_changed = Signal(object)  # FilterState

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(260)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)

        title = QLabel("Filters")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(8)
        scroll.setWidget(container)

        # Errors only
        self._errors_only = QCheckBox("Errors only")
        self._errors_only.toggled.connect(self._emit)
        layout.addWidget(self._errors_only)

        # Level filter
        lvl_box = QGroupBox("Level")
        lvl_layout = QVBoxLayout(lvl_box)
        self._level_checks: dict[str, QCheckBox] = {}
        for lvl in LEVELS_ORDERED:
            cb = QCheckBox(lvl)
            cb.toggled.connect(self._emit)
            self._level_checks[lvl] = cb
            lvl_layout.addWidget(cb)
        layout.addWidget(lvl_box)

        # Time range
        time_box = QGroupBox("Time Range")
        time_layout = QVBoxLayout(time_box)
        time_layout.addWidget(QLabel("From:"))
        self._start_dt = QDateTimeEdit()
        self._start_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._start_dt.setCalendarPopup(True)
        self._start_dt.setSpecialValueText("(any)")
        self._start_dt.setMinimumDateTime(QDateTime(1970, 1, 1, 0, 0, 0))
        time_layout.addWidget(self._start_dt)
        time_layout.addWidget(QLabel("To:"))
        self._end_dt = QDateTimeEdit()
        self._end_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._end_dt.setCalendarPopup(True)
        self._end_dt.setSpecialValueText("(any)")
        self._end_dt.setMinimumDateTime(QDateTime(1970, 1, 1, 0, 0, 0))
        time_layout.addWidget(self._end_dt)
        self._use_time = QCheckBox("Enable time filter")
        self._use_time.toggled.connect(self._on_time_toggle)
        time_layout.addWidget(self._use_time)
        self._start_dt.setEnabled(False)
        self._end_dt.setEnabled(False)
        self._start_dt.dateTimeChanged.connect(self._emit)
        self._end_dt.dateTimeChanged.connect(self._emit)
        layout.addWidget(time_box)

        # Field filters
        field_box = QGroupBox("Field Filters")
        field_layout = QVBoxLayout(field_box)

        field_layout.addWidget(QLabel("Hostname:"))
        self._host_edit = QLineEdit()
        self._host_edit.setPlaceholderText("contains…")
        self._host_edit.textChanged.connect(self._emit)
        field_layout.addWidget(self._host_edit)

        field_layout.addWidget(QLabel("User:"))
        self._user_edit = QLineEdit()
        self._user_edit.textChanged.connect(self._emit)
        field_layout.addWidget(self._user_edit)

        field_layout.addWidget(QLabel("Correlation ID:"))
        self._corr_edit = QLineEdit()
        self._corr_edit.textChanged.connect(self._emit)
        field_layout.addWidget(self._corr_edit)

        field_layout.addWidget(QLabel("PID:"))
        self._pid_edit = QLineEdit()
        self._pid_edit.textChanged.connect(self._emit)
        field_layout.addWidget(self._pid_edit)

        field_layout.addWidget(QLabel("Exclude (comma-sep):"))
        self._exclude_edit = QLineEdit()
        self._exclude_edit.setPlaceholderText("health,ping,…")
        self._exclude_edit.textChanged.connect(self._emit)
        field_layout.addWidget(self._exclude_edit)

        layout.addWidget(field_box)

        # Actions
        clear_btn = QPushButton("Clear All Filters")
        clear_btn.clicked.connect(self.clear_all)
        layout.addWidget(clear_btn)

        layout.addStretch()

    def _on_time_toggle(self, enabled: bool) -> None:
        self._start_dt.setEnabled(enabled)
        self._end_dt.setEnabled(enabled)
        self._emit()

    def _emit(self, *_) -> None:
        self.filter_changed.emit(self.current_filter())

    def current_filter(self) -> FilterState:
        f = FilterState()
        f.errors_only = self._errors_only.isChecked()
        f.levels = [lvl for lvl, cb in self._level_checks.items() if cb.isChecked()]

        if self._use_time.isChecked():
            sdt = self._start_dt.dateTime()
            edt = self._end_dt.dateTime()
            null_dt = QDateTime(1970, 1, 1, 0, 0, 0)
            if sdt != null_dt:
                f.start_time = sdt.toPython()
            if edt != null_dt:
                f.end_time = edt.toPython()

        f.hostname = self._host_edit.text().strip()
        f.user = self._user_edit.text().strip()
        f.correlation_id = self._corr_edit.text().strip()
        f.pid = self._pid_edit.text().strip()

        raw_excl = self._exclude_edit.text()
        f.exclude_expressions = [x.strip() for x in raw_excl.split(",") if x.strip()]
        return f

    def clear_all(self) -> None:
        self._errors_only.setChecked(False)
        for cb in self._level_checks.values():
            cb.setChecked(False)
        self._use_time.setChecked(False)
        self._host_edit.clear()
        self._user_edit.clear()
        self._corr_edit.clear()
        self._pid_edit.clear()
        self._exclude_edit.clear()
        self._emit()
