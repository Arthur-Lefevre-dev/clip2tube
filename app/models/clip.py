"""Clip domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Clip:
    """Represents a Twitch clip ready for selection / processing."""

    id: str
    title: str
    url: str
    embed_url: str
    thumbnail_url: str
    broadcaster_id: str
    broadcaster_name: str
    creator_name: str
    game_id: str = ""
    game_name: str = ""
    view_count: int = 0
    duration: float = 0.0
    created_at: Optional[datetime] = None
    language: str = "en"
    # Local path after download (filled later)
    local_path: str = ""
    # Whether this clip was already processed (history check)
    already_processed: bool = False
    # Extra metadata for UI
    selected: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def duration_label(self) -> str:
        """Human-readable duration (e.g. 0:45)."""
        seconds = int(round(self.duration))
        minutes, secs = divmod(seconds, 60)
        return f"{minutes}:{secs:02d}"

    @property
    def views_label(self) -> str:
        """Compact view count for list display."""
        if self.view_count >= 1_000_000:
            return f"{self.view_count / 1_000_000:.1f}M"
        if self.view_count >= 1_000:
            return f"{self.view_count / 1_000:.1f}K"
        return str(self.view_count)
