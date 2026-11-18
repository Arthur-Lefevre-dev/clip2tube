"""Publication / processing job model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from .region import FacecamRegion


class JobStatus(str, Enum):
    """Lifecycle status for a processing / publish job."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    SUBTITLING = "subtitling"
    QUEUED = "queued"
    UPLOADING = "uploading"
    PUBLISHED = "published"
    ERROR = "error"
    CANCELLED = "cancelled"


class LayoutType(str, Enum):
    """Vertical video layout presets."""

    BLUR_CENTER = "blur_center"  # Gameplay centered + blurred background
    FACECAM_SPLIT = "facecam_split"  # Facecam top + gameplay bottom
    LETTERBOX = "letterbox"  # 16:9 centered with black bars + title


@dataclass
class Job:
    """A single clip-to-publish pipeline job."""

    id: str
    clip_id: str
    clip_title: str
    streamer: str
    game_name: str = ""
    status: JobStatus = JobStatus.PENDING
    layout: LayoutType = LayoutType.BLUR_CENTER
    facecam_region: Optional[FacecamRegion] = None
    output_path: str = ""
    source_path: str = ""
    youtube_title: str = ""
    youtube_description: str = ""
    tiktok_caption: str = ""
    publish_youtube: bool = True
    publish_tiktok: bool = True
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    youtube_video_id: str = ""
    tiktok_publish_id: str = ""
    error_message: str = ""
    progress: float = 0.0  # 0.0 – 100.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    logs: list[str] = field(default_factory=list)
