"""Application path helpers."""

from __future__ import annotations

import sys
from pathlib import Path


def get_app_root() -> Path:
    """
    Return the project / installation root.

    When frozen by PyInstaller, use the executable directory.
    Otherwise use the repository root (parent of ``app/``).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # app/utils/paths.py -> app/utils -> app -> project root
    return Path(__file__).resolve().parents[2]


def get_config_dir() -> Path:
    """Directory that holds config.json and credentials."""
    return get_app_root() / "config"


def get_data_dir() -> Path:
    """Directory for SQLite DB, tokens, and runtime data."""
    return get_app_root() / "data"


def get_output_dir() -> Path:
    """Default folder for rendered vertical videos."""
    return get_app_root() / "output"


def ensure_dirs() -> None:
    """Create required runtime directories if they do not exist."""
    for path in (
        get_config_dir(),
        get_data_dir(),
        get_output_dir(),
        get_app_root() / "music",
        get_app_root() / "temp",
    ):
        path.mkdir(parents=True, exist_ok=True)
