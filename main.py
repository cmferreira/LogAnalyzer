import sys
import os

# Ensure the project root is in sys.path when running as a script
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.config.config_manager import ConfigManager
from app.ui.main_window import MainWindow
from app.ui.theme_manager import apply_theme


def main() -> None:
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("LogAnalyzer")
    app.setOrganizationName("LogAnalyzer")

    cfg = ConfigManager.instance()
    apply_theme(app, cfg.theme)

    window = MainWindow()
    window.show()

    # Handle file paths passed as CLI arguments
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            window._load_file(arg)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
