"""Clip2Tube entry point — Windows desktop app (PySide6)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Avoid Qt plugin issues on some Windows setups
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

# When frozen by PyInstaller, help Qt find its plugins
if getattr(sys, "frozen", False):
    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    plugin_candidates = [
        base / "PySide6" / "plugins",
        Path(sys.executable).resolve().parent / "_internal" / "PySide6" / "plugins",
    ]
    for candidate in plugin_candidates:
        if candidate.is_dir():
            os.environ.setdefault("QT_PLUGIN_PATH", str(candidate))
            break


from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.db import Database
from app.ui.main_window import MainWindow, load_app_icon
from app.ui.theme import apply_theme
from app.utils.config import load_config
from app.utils.paths import ensure_dirs


def main() -> int:
    """Boot the Qt application and show the main window."""
    ensure_dirs()
    config = load_config()
    database = Database()
    database.initialize()

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Clip2Tube")
    app.setOrganizationName("Clip2Tube")
    app.setWindowIcon(load_app_icon())
    app.setQuitOnLastWindowClosed(False)  # keep alive for system tray
    apply_theme(app)

    window = MainWindow(config=config, database=database)
    window.show()

    exit_code = app.exec()
    database.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
