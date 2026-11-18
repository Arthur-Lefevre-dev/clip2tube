"""Connected platform account model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Platform(str, Enum):
    """Supported publishing platforms."""

    YOUTUBE = "youtube"
    TIKTOK = "tiktok"


@dataclass
class Account:
    """OAuth-linked publishing account."""

    id: str
    platform: Platform
    display_name: str
    channel_id: str = ""
    avatar_url: str = ""
    # Encrypted token blob stored in DB / local file — never log this
    token_encrypted: bytes = b""
    connected_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    extra: dict = field(default_factory=dict)
