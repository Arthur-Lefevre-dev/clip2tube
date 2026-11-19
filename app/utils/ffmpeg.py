"""Locate FFmpeg / FFprobe binaries (config path, PATH, or bundled)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from app.utils.paths import get_app_root
from app.utils.process import run_hidden


def _candidate_names(binary: str) -> list[str]:
    if os.name == "nt":
        return [f"{binary}.exe", binary]
    return [binary]


def find_ffmpeg(configured_path: str = "") -> Optional[Path]:
    """
    Resolve ffmpeg executable.

    Order: explicit config path → bundled ``ffmpeg/`` → system PATH.
    """
    return _find_binary("ffmpeg", configured_path)


def find_ffprobe(configured_path: str = "") -> Optional[Path]:
    """Resolve ffprobe next to ffmpeg or on PATH."""
    if configured_path:
        cfg = Path(configured_path)
        if cfg.is_file():
            sibling = cfg.parent / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
            if sibling.is_file():
                return sibling
        elif cfg.is_dir():
            for name in _candidate_names("ffprobe"):
                p = cfg / name
                if p.is_file():
                    return p
    return _find_binary("ffprobe", "")


def _find_binary(name: str, configured_path: str) -> Optional[Path]:
    if configured_path:
        p = Path(configured_path)
        # Accept a direct path to the executable
        if p.is_file():
            return p
        # Or a folder that contains the executable
        if p.is_dir():
            for candidate in _candidate_names(name):
                full = p / candidate
                if full.is_file():
                    return full

    # Bundled next to app / in ffmpeg/ / bin/
    # IMPORTANT: use is_file() — Path("ffmpeg").exists() is True for the folder
    # named ffmpeg/ and would otherwise be returned as the "binary".
    root = get_app_root()
    for folder in (root / "ffmpeg", root / "bin", root):
        for candidate in _candidate_names(name):
            full = folder / candidate
            if full.is_file():
                return full

    which = shutil.which(name)
    if which:
        path = Path(which)
        if path.is_file():
            return path
    return None


def run_ffmpeg(
    args: list[str],
    ffmpeg_path: Optional[Path] = None,
    timeout: Optional[int] = None,
) -> subprocess.CompletedProcess[str]:
    """Run ffmpeg with given args (without the binary name)."""
    binary = ffmpeg_path or find_ffmpeg()
    if binary is None or not binary.is_file():
        raise FileNotFoundError(
            "FFmpeg introuvable. Indiquez le chemin dans Paramètres "
            "ou placez ffmpeg.exe dans le dossier ffmpeg/."
        )
    cmd = [str(binary), "-hide_banner", "-loglevel", "error", "-y", *args]
    return run_hidden(cmd, timeout=timeout, check=False)


def probe_duration(video_path: Path, ffprobe_path: Optional[Path] = None) -> float:
    """Return media duration in seconds via ffprobe."""
    binary = ffprobe_path or find_ffprobe()
    if binary is None:
        return 0.0
    result = run_hidden(
        [
            str(binary),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0
