from __future__ import annotations
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt


def _load_qss(name: str) -> str:
    here = os.path.dirname(__file__)
    styles_dir = os.path.join(here, "..", "..", "resources", "styles")
    path = os.path.join(styles_dir, f"{name}.qss")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def apply_theme(app: QApplication, theme: str) -> None:
    if theme == "dark":
        _apply_dark(app)
    else:
        _apply_light(app)


def _apply_dark(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    dark = QColor(30, 30, 30)
    darker = QColor(20, 20, 20)
    mid = QColor(45, 45, 45)
    text = QColor(212, 212, 212)
    highlight = QColor(0, 120, 212)
    disabled = QColor(100, 100, 100)

    palette.setColor(QPalette.ColorRole.Window, dark)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, darker)
    palette.setColor(QPalette.ColorRole.AlternateBase, mid)
    palette.setColor(QPalette.ColorRole.ToolTipBase, mid)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, mid)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link, highlight)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)

    app.setPalette(palette)
    qss = _load_qss("dark")
    if qss:
        app.setStyleSheet(qss)


def _apply_light(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setPalette(QApplication.style().standardPalette())
    qss = _load_qss("light")
    if qss:
        app.setStyleSheet(qss)
