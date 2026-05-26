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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self._label = QLabel("Search:")
        layout.addWidget(self._label)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Search logs… (Ctrl+F)")
        self._edit.setClearButtonEnabled(True)
        self._edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._edit)

        self._regex_btn = QToolButton()
        self._regex_btn.setText(".*")
        self._regex_btn.setCheckable(True)
        self._regex_btn.setToolTip("Regex mode")
        self._regex_btn.toggled.connect(self._emit_search)
        layout.addWidget(self._regex_btn)

        self._case_btn = QToolButton()
        self._case_btn.setText("Aa")
        self._case_btn.setCheckable(True)
        self._case_btn.setToolTip("Case sensitive")
        self._case_btn.toggled.connect(self._emit_search)
        layout.addWidget(self._case_btn)

        self._clear_btn = QToolButton()
        self._clear_btn.setText("✕")
        self._clear_btn.setToolTip("Clear search")
        self._clear_btn.clicked.connect(self.clear)
        layout.addWidget(self._clear_btn)

        self._count_label = QLabel("")
        self._count_label.setMinimumWidth(80)
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
