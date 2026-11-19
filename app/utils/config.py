"""Load and persist application configuration (config.json)."""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import get_config_dir, ensure_dirs


DEFAULT_CONFIG: dict[str, Any] = {
    "twitch": {"client_id": "", "client_secret": ""},
    "google": {"client_id": "", "client_secret": ""},
    "tiktok": {"client_key": "", "client_secret": ""},
    "ffmpeg_path": "",
    "output_dir": "output",
    "music_dir": "music",
    "video_quality": "high",
    "followed_streamers": [],
    "auto_pilot": {
        "enabled": False,
        "interval_hours": 6,
        "max_publications_per_day": 5,
    },
    "updates": {
        "check_on_startup": True,
        "github_repo": "Arthur-Lefevre-dev/clip2tube",
    },
    "defaults": {
        "layout": "blur_center",
        "facecam_region": {
            "x": 0.70,
            "y": 0.05,
            "w": 0.28,
            "h": 0.40,
            "top_ratio": 0.33,
            "width_ratio": 0.66,
        },
        "max_clip_duration": 60,
        "whisper_model": "small",
        "whisper_language": "auto",
        "whisper_use_gpu": True,
        "subtitles_enabled": True,
        "burn_title_overlay": False,
        "title_font": "Arial",
        "title_color": "#FFFFFF",
        "subtitle_font": "Arial",
        "subtitle_color": "#FFFFFF",
        "music_volume": 0.15,
        "youtube_title_template": "{titre_clip} #Shorts",
        "youtube_description_template": (
            "Clip de {streamer} - twitch.tv/{streamer}\n\n{hashtags}"
        ),
        "tiktok_caption_template": (
            "{titre_clip} | Clip de {streamer} {hashtags}"
        ),
    },
}


@dataclass
class AppConfig:
    """Typed wrapper around the JSON config file."""

    raw: dict[str, Any] = field(default_factory=lambda: deepcopy(DEFAULT_CONFIG))
    path: Path = field(default_factory=lambda: get_config_dir() / "config.json")

    def get(self, *keys: str, default: Any = None) -> Any:
        """Nested dict get: ``cfg.get("twitch", "client_id")``."""
        node: Any = self.raw
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, *keys_and_value: Any) -> None:
        """
        Nested dict set.

        Usage: ``cfg.set("twitch", "client_id", "abc")``
        Last argument is the value to assign.
        """
        if len(keys_and_value) < 2:
            raise ValueError("Need at least one key and a value")
        *keys, value = keys_and_value
        node = self.raw
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base without dropping missing default keys."""
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None) -> AppConfig:
    """
    Load config.json, creating it from the example / defaults if missing.
    """
    ensure_dirs()
    config_path = path or (get_config_dir() / "config.json")
    example_path = get_config_dir() / "config.example.json"

    if not config_path.exists():
        if example_path.exists():
            shutil.copy(example_path, config_path)
        else:
            config_path.write_text(
                json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    with config_path.open(encoding="utf-8") as fh:
        loaded = json.load(fh)

    merged = _deep_merge(DEFAULT_CONFIG, loaded)
    return AppConfig(raw=merged, path=config_path)


def save_config(config: AppConfig) -> None:
    """Persist the current configuration to disk."""
    ensure_dirs()
    with config.path.open("w", encoding="utf-8") as fh:
        json.dump(config.raw, fh, indent=2, ensure_ascii=False)
