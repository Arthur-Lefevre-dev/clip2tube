"""SQLite persistence for clip history, jobs, accounts, and logs."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.models import Account, Job, JobStatus, LayoutType, Platform
from app.utils.paths import get_data_dir, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS clip_history (
    clip_id     TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    streamer    TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    output_path TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    clip_id         TEXT NOT NULL,
    clip_title      TEXT NOT NULL,
    streamer        TEXT NOT NULL,
    game_name       TEXT DEFAULT '',
    status          TEXT NOT NULL,
    layout          TEXT NOT NULL,
    output_path     TEXT DEFAULT '',
    source_path     TEXT DEFAULT '',
    youtube_title   TEXT DEFAULT '',
    youtube_description TEXT DEFAULT '',
    tiktok_caption  TEXT DEFAULT '',
    publish_youtube INTEGER DEFAULT 1,
    publish_tiktok  INTEGER DEFAULT 1,
    scheduled_at    TEXT,
    published_at    TEXT,
    youtube_video_id TEXT DEFAULT '',
    tiktok_publish_id TEXT DEFAULT '',
    error_message   TEXT DEFAULT '',
    progress        REAL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id              TEXT PRIMARY KEY,
    platform        TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    channel_id      TEXT DEFAULT '',
    avatar_url      TEXT DEFAULT '',
    token_encrypted BLOB,
    connected_at    TEXT,
    last_used_at    TEXT,
    is_active       INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS app_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    level       TEXT NOT NULL,
    source      TEXT NOT NULL,
    message     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_stats (
    day         TEXT PRIMARY KEY,
    published   INTEGER DEFAULT 0
);
"""


def _now() -> str:
    return datetime.utcnow().isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class Database:
    """Thread-safe SQLite wrapper used by services and the UI."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        ensure_dirs()
        self.path = db_path or (get_data_dir() / "clip2tube.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()

    def connect(self) -> sqlite3.Connection:
        """Return the shared connection (caller must already hold ``_lock``)."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.path),
                check_same_thread=False,
                isolation_level=None,  # autocommit — avoids stale transactions
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
        return self._conn

    def initialize(self) -> None:
        with self._lock:
            conn = self.connect()
            conn.executescript(SCHEMA)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            if "source_path" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN source_path TEXT DEFAULT ''")

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------ clips
    def is_clip_processed(self, clip_id: str) -> bool:
        with self._lock:
            row = self.connect().execute(
                "SELECT 1 FROM clip_history WHERE clip_id = ? LIMIT 1",
                (clip_id,),
            ).fetchone()
            return row is not None

    def mark_clip_processed(
        self, clip_id: str, title: str, streamer: str, output_path: str = ""
    ) -> None:
        with self._lock:
            self.connect().execute(
                """
                INSERT INTO clip_history (clip_id, title, streamer, processed_at, output_path)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(clip_id) DO UPDATE SET
                    title=excluded.title,
                    streamer=excluded.streamer,
                    processed_at=excluded.processed_at,
                    output_path=excluded.output_path
                """,
                (clip_id, title, streamer, _now(), output_path),
            )

    # ------------------------------------------------------------------- jobs
    def upsert_job(self, job: Job) -> None:
        job.updated_at = datetime.utcnow()
        with self._lock:
            self.connect().execute(
                """
                INSERT INTO jobs (
                    id, clip_id, clip_title, streamer, game_name, status, layout,
                    output_path, source_path, youtube_title, youtube_description,
                    tiktok_caption, publish_youtube, publish_tiktok, scheduled_at,
                    published_at, youtube_video_id, tiktok_publish_id, error_message,
                    progress, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(id) DO UPDATE SET
                    clip_title=excluded.clip_title,
                    streamer=excluded.streamer,
                    game_name=excluded.game_name,
                    status=excluded.status,
                    layout=excluded.layout,
                    output_path=excluded.output_path,
                    source_path=excluded.source_path,
                    youtube_title=excluded.youtube_title,
                    youtube_description=excluded.youtube_description,
                    tiktok_caption=excluded.tiktok_caption,
                    publish_youtube=excluded.publish_youtube,
                    publish_tiktok=excluded.publish_tiktok,
                    scheduled_at=excluded.scheduled_at,
                    published_at=excluded.published_at,
                    youtube_video_id=excluded.youtube_video_id,
                    tiktok_publish_id=excluded.tiktok_publish_id,
                    error_message=excluded.error_message,
                    progress=excluded.progress,
                    updated_at=excluded.updated_at
                """,
                (
                    job.id,
                    job.clip_id,
                    job.clip_title,
                    job.streamer,
                    job.game_name,
                    job.status.value,
                    job.layout.value,
                    job.output_path,
                    getattr(job, "source_path", ""),
                    job.youtube_title,
                    job.youtube_description,
                    job.tiktok_caption,
                    1 if job.publish_youtube else 0,
                    1 if job.publish_tiktok else 0,
                    job.scheduled_at.isoformat() if job.scheduled_at else None,
                    job.published_at.isoformat() if job.published_at else None,
                    job.youtube_video_id,
                    job.tiktok_publish_id,
                    job.error_message,
                    job.progress,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                ),
            )

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            row = self.connect().execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            return self._row_to_job(row) if row else None

    def list_jobs(self, limit: int = 200) -> list[Job]:
        with self._lock:
            rows = self.connect().execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_job(r) for r in rows]

    def delete_job(self, job_id: str) -> None:
        with self._lock:
            self.connect().execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def delete_all_jobs(self) -> int:
        with self._lock:
            cur = self.connect().execute("DELETE FROM jobs")
            return int(cur.rowcount or 0)

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        keys = row.keys()
        job = Job(
            id=row["id"],
            clip_id=row["clip_id"],
            clip_title=row["clip_title"],
            streamer=row["streamer"],
            game_name=row["game_name"] or "",
            status=JobStatus(row["status"]),
            layout=LayoutType(row["layout"]),
            output_path=row["output_path"] or "",
            youtube_title=row["youtube_title"] or "",
            youtube_description=row["youtube_description"] or "",
            tiktok_caption=row["tiktok_caption"] or "",
            publish_youtube=bool(row["publish_youtube"]),
            publish_tiktok=bool(row["publish_tiktok"]),
            scheduled_at=_parse_dt(row["scheduled_at"]),
            published_at=_parse_dt(row["published_at"]),
            youtube_video_id=row["youtube_video_id"] or "",
            tiktok_publish_id=row["tiktok_publish_id"] or "",
            error_message=row["error_message"] or "",
            progress=float(row["progress"] or 0),
            created_at=_parse_dt(row["created_at"]) or datetime.utcnow(),
            updated_at=_parse_dt(row["updated_at"]) or datetime.utcnow(),
        )
        job.source_path = (row["source_path"] or "") if "source_path" in keys else ""
        return job

    # --------------------------------------------------------------- accounts
    def upsert_account(self, account: Account) -> None:
        with self._lock:
            self.connect().execute(
                """
                INSERT INTO accounts (
                    id, platform, display_name, channel_id, avatar_url,
                    token_encrypted, connected_at, last_used_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name=excluded.display_name,
                    channel_id=excluded.channel_id,
                    avatar_url=excluded.avatar_url,
                    token_encrypted=excluded.token_encrypted,
                    connected_at=excluded.connected_at,
                    last_used_at=excluded.last_used_at,
                    is_active=excluded.is_active
                """,
                (
                    account.id,
                    account.platform.value,
                    account.display_name,
                    account.channel_id,
                    account.avatar_url,
                    account.token_encrypted,
                    account.connected_at.isoformat() if account.connected_at else None,
                    account.last_used_at.isoformat() if account.last_used_at else None,
                    1 if account.is_active else 0,
                ),
            )

    def get_account(self, platform: Platform) -> Optional[Account]:
        with self._lock:
            row = self.connect().execute(
                "SELECT * FROM accounts WHERE platform = ? AND is_active = 1 LIMIT 1",
                (platform.value,),
            ).fetchone()
            if not row:
                return None
            return Account(
                id=row["id"],
                platform=Platform(row["platform"]),
                display_name=row["display_name"],
                channel_id=row["channel_id"] or "",
                avatar_url=row["avatar_url"] or "",
                token_encrypted=row["token_encrypted"] or b"",
                connected_at=_parse_dt(row["connected_at"]),
                last_used_at=_parse_dt(row["last_used_at"]),
                is_active=bool(row["is_active"]),
            )

    def delete_account(self, platform: Platform) -> None:
        with self._lock:
            self.connect().execute(
                "DELETE FROM accounts WHERE platform = ?", (platform.value,)
            )

    # ------------------------------------------------------------------- logs
    def add_log(self, level: str, source: str, message: str) -> None:
        with self._lock:
            self.connect().execute(
                "INSERT INTO app_log (created_at, level, source, message) VALUES (?, ?, ?, ?)",
                (_now(), level, source, message),
            )

    def list_logs(self, limit: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connect().execute(
                "SELECT * FROM app_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_logs(self) -> None:
        with self._lock:
            self.connect().execute("DELETE FROM app_log")

    # ----------------------------------------------------------- daily quota
    def publications_today(self) -> int:
        day = datetime.utcnow().strftime("%Y-%m-%d")
        with self._lock:
            row = self.connect().execute(
                "SELECT published FROM daily_stats WHERE day = ?", (day,)
            ).fetchone()
            return int(row["published"]) if row else 0

    def increment_publications_today(self, count: int = 1) -> None:
        day = datetime.utcnow().strftime("%Y-%m-%d")
        with self._lock:
            self.connect().execute(
                """
                INSERT INTO daily_stats (day, published) VALUES (?, ?)
                ON CONFLICT(day) DO UPDATE SET published = published + excluded.published
                """,
                (day, count),
            )
