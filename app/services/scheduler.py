"""Publication queue + auto-pilot scheduler."""

from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import QObject, QTimer, Signal

from app.db import Database
from app.models import Clip, Job, JobStatus, LayoutType
from app.services.pipeline import PipelineService
from app.services.twitch import TwitchService
from app.utils.config import AppConfig, save_config


class SchedulerService(QObject):
    """Manage the publish queue and optional auto-pilot loop."""

    job_updated = Signal(object)  # Job
    log_message = Signal(str)
    autopilot_tick = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        database: Database,
        pipeline: PipelineService,
        twitch: TwitchService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.database = database
        self.pipeline = pipeline
        self.twitch = twitch
        self._running = False
        self._busy = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._publish_timer = QTimer(self)
        self._publish_timer.setInterval(30_000)  # check scheduled every 30s
        self._publish_timer.timeout.connect(self._flush_due_jobs)
        self._publish_timer.start()

    @property
    def is_running(self) -> bool:
        return self._running

    def start_auto_pilot(self) -> None:
        hours = float(
            self.config.get("auto_pilot", "interval_hours", default=6) or 6
        )
        ms = max(int(hours * 3600 * 1000), 60_000)
        self._running = True
        self.config.set("auto_pilot", "enabled", True)
        save_config(self.config)
        self._timer.start(ms)
        self.log_message.emit(f"Auto-pilote démarré (toutes les {hours} h).")
        self._run_autopilot_cycle()

    def stop_auto_pilot(self) -> None:
        self._running = False
        self._timer.stop()
        self.config.set("auto_pilot", "enabled", False)
        save_config(self.config)
        self.log_message.emit("Auto-pilote arrêté.")

    def enqueue(self, job: Job) -> None:
        job.status = JobStatus.QUEUED
        self.database.upsert_job(job)
        self.job_updated.emit(job)

    def retry(self, job_id: str) -> None:
        job = self.database.get_job(job_id)
        if not job:
            return
        job.status = JobStatus.QUEUED
        job.error_message = ""
        job.progress = 0
        self.database.upsert_job(job)
        self.job_updated.emit(job)
        # If video already rendered, just republish; else reprocess
        if job.output_path:
            self.pipeline.publish_job(
                job,
                on_log=lambda m: self.log_message.emit(m),
                on_progress=lambda j: self.job_updated.emit(j),
            )
        else:
            self.pipeline.process_job(
                job,
                on_log=lambda m: self.log_message.emit(m),
                on_progress=lambda j: self.job_updated.emit(j),
            )

    def _on_timer(self) -> None:
        if self._running:
            self._run_autopilot_cycle()

    def _daily_limit_reached(self) -> bool:
        limit = int(
            self.config.get("auto_pilot", "max_publications_per_day", default=5) or 5
        )
        return self.database.publications_today() >= limit

    def _run_autopilot_cycle(self) -> None:
        if self._busy:
            return
        if self._daily_limit_reached():
            msg = "Limite quotidienne de publications atteinte."
            self.log_message.emit(msg)
            self.autopilot_tick.emit(msg)
            return

        streamers = list(self.config.get("followed_streamers", default=[]) or [])
        if not streamers:
            msg = "Aucun streamer suivi — configurez la liste dans Paramètres."
            self.log_message.emit(msg)
            self.autopilot_tick.emit(msg)
            return

        if not self.twitch.is_configured():
            self.log_message.emit("Twitch non configuré — auto-pilote en pause.")
            return

        self._busy = True
        try:
            self.autopilot_tick.emit("Cycle auto-pilote…")
            max_per = max(
                1,
                int(
                    self.config.get("auto_pilot", "max_publications_per_day", default=5)
                    or 5
                )
                - self.database.publications_today(),
            )
            defaults = self.config.get("defaults", default={}) or {}
            layout = LayoutType(defaults.get("layout", LayoutType.BLUR_CENTER.value))
            max_duration = float(defaults.get("max_clip_duration", 60) or 60)

            collected: list[Clip] = []
            for login in streamers:
                if len(collected) >= max_per:
                    break
                try:
                    clips = self.twitch.search_clips(
                        login,
                        period="24h",
                        max_clips=5,
                        max_duration=max_duration,
                    )
                except Exception as exc:
                    self.log_message.emit(f"Auto Twitch ({login}): {exc}")
                    continue
                for clip in clips:
                    if self.database.is_clip_processed(clip.id):
                        continue
                    collected.append(clip)
                    if len(collected) >= max_per:
                        break

            if not collected:
                self.autopilot_tick.emit("Aucun nouveau clip.")
                return

            for clip in collected:
                if self._daily_limit_reached():
                    break
                job = self.pipeline.create_job_from_clip(clip, layout=layout)
                self.log_message.emit(f"Auto: traitement {clip.title}")
                self.pipeline.process_job(
                    job,
                    clip_url=clip.url,
                    on_log=lambda m: self.log_message.emit(m),
                    on_progress=lambda j: self.job_updated.emit(j),
                )
            self.autopilot_tick.emit(f"Cycle terminé ({len(collected)} clip(s)).")
        finally:
            self._busy = False

    def _flush_due_jobs(self) -> None:
        """Publish queued jobs whose schedule is due."""
        if self._busy:
            return
        now = datetime.utcnow()
        for job in self.database.list_jobs(100):
            if job.status != JobStatus.QUEUED:
                continue
            if job.scheduled_at and job.scheduled_at > now:
                continue
            if not job.output_path:
                continue
            self._busy = True
            try:
                self.pipeline.publish_job(
                    job,
                    on_log=lambda m: self.log_message.emit(m),
                    on_progress=lambda j: self.job_updated.emit(j),
                )
            finally:
                self._busy = False
            break  # one at a time
