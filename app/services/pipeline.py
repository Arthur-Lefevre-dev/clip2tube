"""End-to-end job pipeline: download → edit → subtitles → publish."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

from app.db import Database
from app.models import Clip, Job, JobStatus, LayoutType, layout_needs_facecam
from app.models.region import FacecamRegion
from app.services.downloader import DownloaderService
from app.services.subtitles import SubtitlesService
from app.services.tiktok import TikTokService
from app.services.video_editor import VideoEditorService
from app.services.youtube import YouTubeService
from app.utils.config import AppConfig
from app.utils.paths import get_app_root, ensure_dirs
from app.utils.templates import ensure_shorts_hashtag, render_template

LogCallback = Callable[[str], None]
ProgressCallback = Callable[[Job], None]


class PipelineService:
    """Process a single job through the full media pipeline."""

    def __init__(
        self,
        config: AppConfig,
        database: Database,
        youtube: YouTubeService,
        tiktok: TikTokService,
    ) -> None:
        self.config = config
        self.database = database
        self.youtube = youtube
        self.tiktok = tiktok
        self.downloader = DownloaderService()
        ffmpeg = str(config.get("ffmpeg_path", default="") or "")
        self.editor = VideoEditorService(ffmpeg_path=ffmpeg)
        self.subtitles = SubtitlesService(ffmpeg_path=ffmpeg)

    def _output_dir(self) -> Path:
        raw = self.config.get("output_dir", default="output") or "output"
        path = Path(raw)
        if not path.is_absolute():
            path = get_app_root() / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _temp_dir(self) -> Path:
        path = get_app_root() / "temp"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_job_from_clip(
        self,
        clip: Clip,
        layout: LayoutType | None = None,
        publish_youtube: bool = True,
        publish_tiktok: bool = True,
        scheduled_at: datetime | None = None,
        music_path: Path | None = None,
        facecam_region: FacecamRegion | None = None,
    ) -> Job:
        defaults = self.config.get("defaults", default={}) or {}
        layout_val = layout or LayoutType(
            defaults.get("layout", LayoutType.BLUR_CENTER.value)
        )
        if facecam_region is None and layout_needs_facecam(layout_val):
            facecam_region = FacecamRegion.from_dict(
                defaults.get("facecam_region")
            )
        yt_title = ensure_shorts_hashtag(
            render_template(
                defaults.get("youtube_title_template", "{titre_clip} #Shorts"),
                streamer=clip.broadcaster_name,
                jeu=clip.game_name,
                titre_clip=clip.title,
            )
        )
        yt_desc = render_template(
            defaults.get(
                "youtube_description_template",
                "Clip de {streamer} - twitch.tv/{streamer}\n\n{hashtags}",
            ),
            streamer=clip.broadcaster_name,
            jeu=clip.game_name,
            titre_clip=clip.title,
            hashtags="#Twitch #Shorts #Gaming",
        )
        tt_caption = render_template(
            defaults.get(
                "tiktok_caption_template",
                "{titre_clip} | Clip de {streamer} {hashtags}",
            ),
            streamer=clip.broadcaster_name,
            jeu=clip.game_name,
            titre_clip=clip.title,
            hashtags="#fyp #twitch #gaming",
        )
        job = Job(
            id=str(uuid4()),
            clip_id=clip.id,
            clip_title=clip.title,
            streamer=clip.broadcaster_name,
            game_name=clip.game_name,
            status=JobStatus.PENDING,
            layout=layout_val,
            facecam_region=facecam_region,
            youtube_title=yt_title,
            youtube_description=yt_desc,
            tiktok_caption=tt_caption,
            publish_youtube=publish_youtube,
            publish_tiktok=publish_tiktok,
            scheduled_at=scheduled_at,
        )
        # Stash music in logs/extra via source url on clip
        job.logs = [clip.url]
        if music_path:
            job.logs.append(f"music:{music_path}")
        self.database.upsert_job(job)
        return job

    def process_job(
        self,
        job: Job,
        clip_url: str = "",
        music_path: Path | None = None,
        skip_publish: bool = False,
        on_log: Optional[LogCallback] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Job:
        def log(msg: str, *, persist: bool = True) -> None:
            if persist:
                try:
                    self.database.add_log("INFO", "pipeline", msg)
                except Exception:
                    pass
            if on_log:
                on_log(msg)

        def bump(status: JobStatus, progress: float, message: str = "") -> None:
            job.status = status
            job.progress = progress
            if message:
                job.error_message = ""
                log(message)
            try:
                self.database.upsert_job(job)
            except Exception:
                pass
            if on_progress:
                on_progress(job)

        ensure_dirs()
        defaults = self.config.get("defaults", default={}) or {}
        temp = self._temp_dir()
        out_dir = self._output_dir()

        try:
            # Download
            bump(JobStatus.DOWNLOADING, 5, f"Téléchargement du clip {job.clip_id}…")
            clip = Clip(
                id=job.clip_id,
                title=job.clip_title,
                url=clip_url or f"https://clips.twitch.tv/{job.clip_id}",
                embed_url="",
                thumbnail_url="",
                broadcaster_id="",
                broadcaster_name=job.streamer,
                creator_name="",
                game_name=job.game_name,
            )
            # Progress ticks: UI only (avoid SQLite spam during yt-dlp hooks)
            source = self.downloader.download(
                clip, temp, on_progress=lambda m: log(m, persist=False)
            )
            job.source_path = str(source)

            # Edit
            bump(JobStatus.PROCESSING, 30, "Montage vidéo FFmpeg…")
            edited = out_dir / f"{job.id}_vertical.mp4"
            title_font = defaults.get("title_font", "Arial")
            title_color = defaults.get("title_color", "#FFFFFF")
            music_vol = float(defaults.get("music_volume", 0.15))
            if music_path is None:
                for entry in job.logs:
                    if entry.startswith("music:"):
                        music_path = Path(entry[6:])
                        break

            # Text overlays are off by default (cleaner Shorts look)
            burn_text = bool(defaults.get("burn_title_overlay", False))
            self.editor.render(
                source=source,
                output=edited,
                layout=job.layout,
                title=job.clip_title if burn_text else "",
                streamer=job.streamer if burn_text else "",
                title_font=title_font,
                title_color=title_color,
                music_path=music_path,
                music_volume=music_vol,
                facecam_region=job.facecam_region,
                on_progress=lambda m: log(m),
            )

            final_path = edited
            if defaults.get("subtitles_enabled", True):
                bump(JobStatus.SUBTITLING, 60, "Sous-titres Whisper…")
                subtitled = out_dir / f"{job.id}_final.mp4"
                final_path = self.subtitles.transcribe_and_burn(
                    video_path=edited,
                    output_path=subtitled,
                    language=defaults.get("whisper_language", "auto"),
                    model_size=defaults.get("whisper_model", "small"),
                    font=defaults.get("subtitle_font", "Arial"),
                    color=defaults.get("subtitle_color", "#FFFFFF"),
                    use_gpu=bool(defaults.get("whisper_use_gpu", False)),
                    on_progress=lambda m: log(m),
                )

            job.output_path = str(final_path)
            self.database.mark_clip_processed(
                job.clip_id, job.clip_title, job.streamer, job.output_path
            )

            if skip_publish:
                bump(JobStatus.QUEUED, 100, "Vidéo prête (publication différée).")
                job.status = JobStatus.QUEUED
                self.database.upsert_job(job)
                return job

            # Respect schedule: only upload if due
            if job.scheduled_at and job.scheduled_at > datetime.utcnow():
                bump(
                    JobStatus.QUEUED,
                    90,
                    f"Planifié pour {job.scheduled_at.isoformat()}",
                )
                return job

            return self.publish_job(job, on_log=on_log, on_progress=on_progress)

        except Exception as exc:
            job.status = JobStatus.ERROR
            job.error_message = str(exc)
            job.progress = 0
            self.database.upsert_job(job)
            self.database.add_log("ERROR", "pipeline", str(exc))
            if on_log:
                on_log(f"ERREUR: {exc}")
            if on_progress:
                on_progress(job)
            return job

    def publish_job(
        self,
        job: Job,
        on_log: Optional[LogCallback] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Job:
        def log(msg: str) -> None:
            self.database.add_log("INFO", "publish", msg)
            if on_log:
                on_log(msg)

        try:
            job.status = JobStatus.UPLOADING
            job.progress = 85
            self.database.upsert_job(job)
            if on_progress:
                on_progress(job)

            video = Path(job.output_path)
            if not video.exists():
                raise FileNotFoundError(f"Sortie manquante: {job.output_path}")

            if job.publish_youtube:
                log("Upload YouTube…")
                if not self.youtube.is_connected():
                    raise RuntimeError("YouTube non connecté (onglet Comptes).")
                vid = self.youtube.upload(
                    video,
                    job.youtube_title,
                    job.youtube_description,
                    scheduled_at=job.scheduled_at,
                )
                job.youtube_video_id = vid
                log(f"YouTube OK: {vid}")

            if job.publish_tiktok:
                log("Publication / export TikTok…")
                result = self.tiktok.upload_or_export(
                    video,
                    job.tiktok_caption,
                    force_export=not self.tiktok.is_connected(),
                )
                job.tiktok_publish_id = result
                log(f"TikTok: {result}")

            job.status = JobStatus.PUBLISHED
            job.published_at = datetime.utcnow()
            job.progress = 100
            job.error_message = ""
            self.database.upsert_job(job)
            self.database.increment_publications_today(1)
            if on_progress:
                on_progress(job)
            return job
        except Exception as exc:
            job.status = JobStatus.ERROR
            job.error_message = str(exc)
            self.database.upsert_job(job)
            if on_log:
                on_log(f"ERREUR publication: {exc}")
            if on_progress:
                on_progress(job)
            return job
