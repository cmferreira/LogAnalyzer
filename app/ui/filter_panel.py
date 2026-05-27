from __future__ import annotations
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QListWidget, QListWidgetItem, QLabel,
    QDateTimeEdit, QLineEdit, QPushButton, QScrollArea,
    QFrame, QGridLayout,
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
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Panel title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(32)
        title_bar.setStyleSheet(
            "background-color: #252526; border-bottom: 1px solid #3c3c3c;"
        )
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(10, 0, 6, 0)
        title_bar_layout.setSpacing(4)

        title = QLabel("FILTERS")
        title.setObjectName("panelTitle")
        title.setStyleSheet(
            "color: #858585; font-size: 11px; font-weight: 700; "
            "letter-spacing: 1px; background: transparent; border: none;"
        )
        title_bar_layout.addWidget(title)
        title_bar_layout.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("clearBtn")
        clear_btn.setFlat(True)
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "color: #858585; font-size: 11px; padding: 0 4px; }"
            "QPushButton:hover { color: #cccccc; }"
        )
        clear_btn.clicked.connect(self.clear_all)
        title_bar_layout.addWidget(clear_btn)
        outer.addWidget(title_bar)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        outer.addWidget(scroll)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(14)
        scroll.setWidget(container)

        # ── Quick toggle ──────────────────────────────────────────────
        self._errors_only = QCheckBox("Errors only")
        self._errors_only.toggled.connect(self._emit)
        layout.addWidget(self._errors_only)

        # ── Level filter ──────────────────────────────────────────────
        lvl_box = QGroupBox("Level")
        lvl_grid = QGridLayout(lvl_box)
        lvl_grid.setContentsMargins(0, 10, 0, 4)
        lvl_grid.setHorizontalSpacing(4)
        lvl_grid.setVerticalSpacing(2)
        self._level_checks: dict[str, QCheckBox] = {}
        for i, lvl in enumerate(LEVELS_ORDERED):
            cb = QCheckBox(lvl)
            cb.toggled.connect(self._emit)
            self._level_checks[lvl] = cb
            lvl_grid.addWidget(cb, i // 2, i % 2)
        layout.addWidget(lvl_box)

        # ── Time range ────────────────────────────────────────────────
        time_box = QGroupBox("Time Range")
        time_layout = QVBoxLayout(time_box)
        time_layout.setContentsMargins(0, 10, 0, 4)
        time_layout.setSpacing(4)

        self._use_time = QCheckBox("Enable time filter")
        self._use_time.toggled.connect(self._on_time_toggle)
        time_layout.addWidget(self._use_time)

        lbl_from = QLabel("From")
        lbl_from.setStyleSheet("color: #858585; font-size: 11px;")
        time_layout.addWidget(lbl_from)
        self._start_dt = QDateTimeEdit()
        self._start_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._start_dt.setCalendarPopup(True)
        self._start_dt.setSpecialValueText("(any)")
        self._start_dt.setMinimumDateTime(QDateTime(1970, 1, 1, 0, 0, 0))
        self._start_dt.setEnabled(False)
        self._start_dt.dateTimeChanged.connect(self._emit)
        time_layout.addWidget(self._start_dt)

        lbl_to = QLabel("To")
        lbl_to.setStyleSheet("color: #858585; font-size: 11px;")
        time_layout.addWidget(lbl_to)
        self._end_dt = QDateTimeEdit()
        self._end_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self._end_dt.setCalendarPopup(True)
        self._end_dt.setSpecialValueText("(any)")
        self._end_dt.setMinimumDateTime(QDateTime(1970, 1, 1, 0, 0, 0))
        self._end_dt.setEnabled(False)
        self._end_dt.dateTimeChanged.connect(self._emit)
        time_layout.addWidget(self._end_dt)
        layout.addWidget(time_box)

        # ── Field filters ─────────────────────────────────────────────
        field_box = QGroupBox("Fields")
        field_layout = QVBoxLayout(field_box)
        field_layout.setContentsMargins(0, 10, 0, 4)
        field_layout.setSpacing(4)

        def _field_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #858585; font-size: 11px;")
            return lbl

        field_layout.addWidget(_field_label("Hostname"))
        self._host_edit = QLineEdit()
        self._host_edit.setPlaceholderText("contains…")
        self._host_edit.textChanged.connect(self._emit)
        field_layout.addWidget(self._host_edit)

        field_layout.addWidget(_field_label("User"))
        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("contains…")
        self._user_edit.textChanged.connect(self._emit)
        field_layout.addWidget(self._user_edit)

        field_layout.addWidget(_field_label("Correlation ID"))
        self._corr_edit = QLineEdit()
        self._corr_edit.setPlaceholderText("exact match")
        self._corr_edit.textChanged.connect(self._emit)
        field_layout.addWidget(self._corr_edit)

        field_layout.addWidget(_field_label("PID"))
        self._pid_edit = QLineEdit()
        self._pid_edit.setPlaceholderText("exact number")
        self._pid_edit.textChanged.connect(self._emit)
        field_layout.addWidget(self._pid_edit)

        field_layout.addWidget(_field_label("Exclude (comma-separated)"))
        self._exclude_edit = QLineEdit()
        self._exclude_edit.setPlaceholderText("health,ping,…")
        self._exclude_edit.textChanged.connect(self._emit)
        field_layout.addWidget(self._exclude_edit)

        layout.addWidget(field_box)
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
