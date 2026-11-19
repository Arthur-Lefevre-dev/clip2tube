"""Clip2Tube entry point — Windows desktop app (PySide6)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Avoid Qt plugin issues on some Windows setups
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
# Quiet Qt Multimedia / FFmpeg backend chatter (AV1 MFT probe, Input #0 dumps…)
os.environ.setdefault(
    "QT_LOGGING_RULES",
    "qt.multimedia.ffmpeg.debug=false;qt.multimedia.ffmpeg.warning=false;"
    "qt.multimedia.*=false",
)
# Lower libav log noise when Qt's FFmpeg backend probes files
os.environ.setdefault("AV_LOG_FORCE_NOCOLOR", "1")
os.environ.setdefault("FFREPORT", "")

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
from PySide6.QtCore import Qt, qInstallMessageHandler, QtMsgType

from app.db import Database
from app.ui.main_window import MainWindow, load_app_icon
from app.ui.theme import apply_theme
from app.utils.config import load_config
from app.utils.paths import ensure_dirs


def _qt_message_filter(mode, context, message: str) -> None:  # noqa: ARG001
    """Drop noisy Multimedia/FFmpeg backend lines; keep real warnings/errors."""
    text = message or ""
    noisy = (
        "qt.multimedia.ffmpeg",
        "Using Qt multimedia with FFmpeg",
        "could not find any MFT",
        "could not create MFT",
        "MFT name:",
        "Input #0,",
        "Metadata:",
        "Stream #0:",
        "Duration:",
        "major_brand",
        "handler_name",
        "encoder         :",
        "compatible_brands",
    )
    if any(token in text for token in noisy):
        return
    # Still print genuine critical/fatal Qt messages
    if mode in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        print(text, file=sys.stderr)
    elif mode == QtMsgType.QtWarningMsg and "ffmpeg" not in text.lower():
        print(text, file=sys.stderr)


def main() -> int:
    """Boot the Qt application and show the main window."""
    ensure_dirs()
    config = load_config()
    database = Database()
    database.initialize()

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    qInstallMessageHandler(_qt_message_filter)
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
