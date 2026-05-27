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

    # VS Code-inspired palette  (#1e1e1e base, #252526 surface, #007acc accent)
    bg_base    = QColor(0x1e, 0x1e, 0x1e)   # #1e1e1e
    bg_surface = QColor(0x25, 0x25, 0x26)   # #252526
    bg_raised  = QColor(0x2d, 0x2d, 0x30)   # #2d2d30
    text       = QColor(0xcc, 0xcc, 0xcc)   # #cccccc
    text_muted = QColor(0x85, 0x85, 0x85)   # #858585
    accent     = QColor(0x00, 0x7a, 0xcc)   # #007acc
    disabled   = QColor(0x55, 0x55, 0x55)   # #555555

    palette.setColor(QPalette.ColorRole.Window,          bg_base)
    palette.setColor(QPalette.ColorRole.WindowText,      text)
    palette.setColor(QPalette.ColorRole.Base,            bg_base)
    palette.setColor(QPalette.ColorRole.AlternateBase,   bg_surface)
    palette.setColor(QPalette.ColorRole.ToolTipBase,     bg_surface)
    palette.setColor(QPalette.ColorRole.ToolTipText,     text)
    palette.setColor(QPalette.ColorRole.Text,            text)
    palette.setColor(QPalette.ColorRole.Button,          bg_raised)
    palette.setColor(QPalette.ColorRole.ButtonText,      text)
    palette.setColor(QPalette.ColorRole.BrightText,      QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link,            accent)
    palette.setColor(QPalette.ColorRole.Highlight,       accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.PlaceholderText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)

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
