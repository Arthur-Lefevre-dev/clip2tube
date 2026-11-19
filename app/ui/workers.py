"""Background QThread workers so the UI never blocks."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QThread, Signal

from app.models import Clip, Job, LayoutType


class SearchClipsWorker(QThread):
    finished_ok = Signal(list)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        twitch_service: Any,
        query: str,
        period: str,
        max_clips: int,
        max_duration: float,
        is_game: bool,
        streamers: Optional[list[str]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.twitch = twitch_service
        self.query = query
        self.period = period
        self.max_clips = max_clips
        self.max_duration = max_duration
        self.is_game = is_game
        self.streamers = [s for s in (streamers or []) if s]

    def run(self) -> None:
        try:
            if self.streamers:
                clips = self._search_followed()
            else:
                self.progress.emit("Recherche Twitch…")
                clips = self.twitch.search_clips(
                    self.query,
                    period=self.period,
                    max_clips=self.max_clips,
                    max_duration=self.max_duration,
                    is_game=self.is_game,
                )
            self.finished_ok.emit(clips)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _search_followed(self) -> list:
        """Search each followed streamer, merge, dedupe, sort by views."""
        target = max(1, int(self.max_clips))
        per = max(5, (target // max(1, len(self.streamers))) + 5)
        collected: list = []
        seen: set[str] = set()
        errors: list[str] = []

        for i, login in enumerate(self.streamers, start=1):
            self.progress.emit(
                f"Streamer {i}/{len(self.streamers)} : {login}…"
            )
            try:
                batch = self.twitch.search_clips(
                    login,
                    period=self.period,
                    max_clips=per,
                    max_duration=self.max_duration,
                    is_game=False,
                )
            except Exception as exc:
                errors.append(f"{login}: {exc}")
                continue
            for clip in batch:
                if clip.id in seen:
                    continue
                seen.add(clip.id)
                collected.append(clip)

        collected.sort(key=lambda c: getattr(c, "view_count", 0) or 0, reverse=True)
        if not collected and errors:
            raise RuntimeError(
                "Aucun clip trouvé chez vos streamers suivis.\n"
                + "\n".join(errors[:5])
            )
        return collected[:target]


class ProcessJobWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)
    log = Signal(str)
    progress = Signal(object)

    def __init__(
        self,
        pipeline: Any,
        job: Job,
        clip_url: str = "",
        music_path: Optional[Path] = None,
        skip_publish: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.job = job
        self.clip_url = clip_url
        self.music_path = music_path
        self.skip_publish = skip_publish

    def run(self) -> None:
        try:
            result = self.pipeline.process_job(
                self.job,
                clip_url=self.clip_url,
                music_path=self.music_path,
                skip_publish=self.skip_publish,
                on_log=lambda m: self.log.emit(m),
                on_progress=lambda j: self.progress.emit(j),
            )
            if result.status.value == "error":
                self.failed.emit(result.error_message or "Erreur pipeline")
            else:
                self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class PublishJobWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)
    log = Signal(str)

    def __init__(self, pipeline: Any, job: Job, parent=None) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.job = job

    def run(self) -> None:
        try:
            result = self.pipeline.publish_job(
                self.job,
                on_log=lambda m: self.log.emit(m),
            )
            if result.status.value == "error":
                self.failed.emit(result.error_message or "Erreur publication")
            else:
                self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class OAuthWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, callback, parent=None) -> None:
        super().__init__(parent)
        self.callback = callback

    def run(self) -> None:
        try:
            name = self.callback()
            self.finished_ok.emit(str(name))
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdateCheckWorker(QThread):
    """Query GitHub Releases for a newer Clip2Tube version."""

    finished_ok = Signal(object)  # UpdateInfo
    failed = Signal(str)

    def __init__(
        self,
        current_version: str,
        github_repo: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.current_version = current_version
        self.github_repo = github_repo

    def run(self) -> None:
        try:
            from app.services.updater import check_for_updates

            info = check_for_updates(
                current_version=self.current_version,
                github_repo=self.github_repo,
            )
            self.finished_ok.emit(info)
        except Exception as exc:
            self.failed.emit(str(exc))


class PrepareCropFrameWorker(QThread):
    """Download a clip (if needed) and extract a JPEG frame for crop UI."""

    finished_ok = Signal(str)  # frame path
    failed = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        clip: Clip,
        dest_dir: Path,
        ffmpeg_path: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.clip = clip
        self.dest_dir = dest_dir
        self.ffmpeg_path = ffmpeg_path

    def run(self) -> None:
        try:
            import re

            from app.services.downloader import DownloaderService
            from app.ui.widgets.facecam_crop import extract_frame
            from app.utils.paths import get_app_root

            self.dest_dir.mkdir(parents=True, exist_ok=True)
            safe_id = re.sub(r"[^\w\-]+", "_", self.clip.id)
            existing = list(self.dest_dir.glob(f"{safe_id}.*"))
            existing = [
                p
                for p in existing
                if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}
            ]
            if existing:
                video = existing[0]
                self.progress.emit("Clip déjà téléchargé, extraction de la frame…")
            else:
                self.progress.emit("Téléchargement du clip pour cadrer la cam…")
                video = DownloaderService().download(
                    self.clip,
                    self.dest_dir,
                    on_progress=lambda m: self.progress.emit(m),
                )

            frame = get_app_root() / "temp" / f"{safe_id}_frame.jpg"
            self.progress.emit("Extraction de l'image…")
            extract_frame(video, frame, time_sec=1.0, ffmpeg_path=self.ffmpeg_path)
            self.finished_ok.emit(str(frame))
        except Exception as exc:
            self.failed.emit(str(exc))


class FetchStreamerProfilesWorker(QThread):
    """Resolve Twitch display names + avatar URLs for followed logins."""

    finished_ok = Signal(dict)  # login → {display_name, profile_image_url}
    failed = Signal(str)

    def __init__(self, twitch_service: Any, logins: list[str], parent=None) -> None:
        super().__init__(parent)
        self.twitch = twitch_service
        self.logins = list(logins)

    def run(self) -> None:
        try:
            if not self.twitch or not self.twitch.is_configured():
                self.finished_ok.emit({})
                return
            users = self.twitch.get_users_by_logins(self.logins)
            payload: dict[str, dict[str, str]] = {}
            for login, user in users.items():
                payload[login] = {
                    "display_name": str(user.get("display_name") or login),
                    "profile_image_url": str(user.get("profile_image_url") or ""),
                }
            self.finished_ok.emit(payload)
        except Exception as exc:
            self.failed.emit(str(exc))
