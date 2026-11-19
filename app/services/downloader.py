"""Clip downloader via yt-dlp."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

from app.models import Clip
from app.utils.ffmpeg import find_ffmpeg
from app.utils.paths import get_app_root
from app.utils.process import windows_hidden_kwargs


ProgressCallback = Callable[[str], None]


def _patch_subprocess_no_window() -> None:
    """Ensure child consoles (ffmpeg via yt-dlp) stay hidden on Windows."""
    if getattr(subprocess, "_clip2tube_hidden_patched", False):
        return
    hidden = windows_hidden_kwargs()
    if not hidden:
        return
    original_popen = subprocess.Popen

    def _popen(*args, **kwargs):  # type: ignore[no-untyped-def]
        for key, value in hidden.items():
            if key == "creationflags":
                kwargs["creationflags"] = int(kwargs.get("creationflags", 0)) | int(
                    value
                )
            else:
                kwargs.setdefault(key, value)
        return original_popen(*args, **kwargs)

    subprocess.Popen = _popen  # type: ignore[misc]
    subprocess._clip2tube_hidden_patched = True  # type: ignore[attr-defined]


class DownloaderError(Exception):
    pass


class DownloaderService:
    """Download Twitch clips to a local folder using yt-dlp."""

    def download(
        self,
        clip: Clip,
        dest_dir: Path,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Path:
        try:
            import yt_dlp
        except ImportError as exc:
            raise DownloaderError(
                "yt-dlp n'est pas installé. Lancez: pip install yt-dlp"
            ) from exc

        _patch_subprocess_no_window()

        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^\w\-]+", "_", clip.id)
        outtmpl = str(dest_dir / f"{safe_id}.%(ext)s")

        def hook(d: dict) -> None:
            # Never raise from progress hooks — it aborts the download
            try:
                if not on_progress:
                    return
                if d.get("status") == "downloading":
                    pct = (d.get("_percent_str") or "").strip()
                    on_progress(f"Téléchargement {pct}".strip())
                elif d.get("status") == "finished":
                    on_progress("Téléchargement terminé, finalisation…")
            except Exception:
                pass

        # Disable yt-dlp SQLite cache (avoids "cannot commit - no transaction is active")
        cache_dir = get_app_root() / "temp" / "yt-dlp-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        ydl_opts: dict = {
            "outtmpl": outtmpl,
            "quiet": True,
            "noprogress": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            "retries": 5,
            "fragment_retries": 5,
            "format": "best",
            "cachedir": False,
            "noplaylist": True,
            # Prefer clip page URLs
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        }
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            ydl_opts["ffmpeg_location"] = str(ffmpeg.parent)

        url = clip.url or f"https://clips.twitch.tv/{clip.id}"
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise DownloaderError("Aucune info renvoyée par yt-dlp.")
                filename = ydl.prepare_filename(info)
        except DownloaderError:
            raise
        except Exception as exc:
            raise DownloaderError(f"Échec du téléchargement: {exc}") from exc

        path = Path(filename)
        if not path.exists():
            matches = list(dest_dir.glob(f"{safe_id}.*"))
            # Ignore .part / .ytdl leftovers
            matches = [
                m
                for m in matches
                if m.suffix.lower() not in {".part", ".ytdl", ".temp"}
            ]
            if not matches:
                raise DownloaderError("Fichier téléchargé introuvable.")
            path = matches[0]

        clip.local_path = str(path)
        return path
