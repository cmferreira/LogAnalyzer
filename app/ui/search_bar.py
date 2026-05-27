from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QToolButton,
    QLabel, QComboBox,
)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut


class SearchBar(QWidget):
    search_changed = Signal(str, bool, bool)   # text, regex, case_sensitive
    cleared = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._emit_search)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setFixedHeight(38)
        self.setStyleSheet(
            "SearchBar { background-color: #2d2d30; border-bottom: 1px solid #3c3c3c; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Search logs…  (Ctrl+F)")
        self._edit.setClearButtonEnabled(True)
        self._edit.setFixedHeight(26)
        self._edit.setStyleSheet(
            "QLineEdit {"
            "  background-color: #1e1e1e;"
            "  border: 1px solid #3c3c3c;"
            "  border-radius: 4px;"
            "  padding: 2px 8px;"
            "  font-size: 13px;"
            "  color: #cccccc;"
            "}"
            "QLineEdit:focus {"
            "  border-color: #007acc;"
            "}"
        )
        self._edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._edit, 1)

        _btn_style = (
            "QToolButton {"
            "  background: transparent;"
            "  border: 1px solid transparent;"
            "  border-radius: 3px;"
            "  color: #858585;"
            "  padding: 2px 6px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "}"
            "QToolButton:hover { color: #cccccc; background-color: #3c3c3c; }"
            "QToolButton:checked { color: #007acc; border-color: #007acc; background-color: #0e3a5c; }"
        )

        self._regex_btn = QToolButton()
        self._regex_btn.setText(".*")
        self._regex_btn.setCheckable(True)
        self._regex_btn.setToolTip("Regex mode")
        self._regex_btn.setFixedSize(28, 24)
        self._regex_btn.setStyleSheet(_btn_style)
        self._regex_btn.toggled.connect(self._emit_search)
        layout.addWidget(self._regex_btn)

        self._case_btn = QToolButton()
        self._case_btn.setText("Aa")
        self._case_btn.setCheckable(True)
        self._case_btn.setToolTip("Case sensitive")
        self._case_btn.setFixedSize(28, 24)
        self._case_btn.setStyleSheet(_btn_style)
        self._case_btn.toggled.connect(self._emit_search)
        layout.addWidget(self._case_btn)

        self._count_label = QLabel("")
        self._count_label.setMinimumWidth(100)
        self._count_label.setStyleSheet("color: #858585; font-size: 11px;")
        layout.addWidget(self._count_label)

        shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut.activated.connect(self._edit.setFocus)

    def _on_text_changed(self, _text: str) -> None:
        self._timer.start()

    def _emit_search(self) -> None:
        text = self._edit.text()
        self.search_changed.emit(
            text,
            self._regex_btn.isChecked(),
            self._case_btn.isChecked(),
        )

    def clear(self) -> None:
        self._edit.clear()
        self.cleared.emit()

    def set_result_count(self, count: int, total: int) -> None:
        if self._edit.text():
            self._count_label.setText(f"{count:,} / {total:,}")
        else:
            self._count_label.setText(f"{total:,} entries")

    @property
    def text(self) -> str:
        return self._edit.text()

    def set_focus(self) -> None:
        self._edit.setFocus()
        self._edit.selectAll()
