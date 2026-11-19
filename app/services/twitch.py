"""Twitch Helix API client (Get Clips / users / games)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import requests

from app.models import Clip
from app.utils.config import AppConfig

HELIX = "https://api.twitch.tv/helix"
AUTH = "https://id.twitch.tv/oauth2/token"


class TwitchError(Exception):
    """Raised when Twitch API calls fail."""


def normalize_twitch_query(query: str) -> str:
    """
    Accept a login, display name, or Twitch URL and return a clean query.

    Examples:
      ``xqc`` → ``xqc``
      ``https://www.twitch.tv/xqc`` → ``xqc``
      ``https://twitch.tv/xqc/clip/...`` → ``xqc``
    """
    raw = (query or "").strip()
    if not raw:
        return ""
    if "twitch.tv" in raw.lower():
        try:
            path = urlparse(raw if "://" in raw else f"https://{raw}").path
            parts = [p for p in path.split("/") if p]
            if parts:
                # Skip reserved first segments when relevant
                if parts[0].lower() in {"directory", "videos", "settings"}:
                    return raw
                return parts[0]
        except Exception:
            pass
    # Strip leading @ if pasted from socials
    return re.sub(r"^@", "", raw)


class TwitchService:
    """Fetch clips from the Twitch Helix API."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._access_token: Optional[str] = None
        self._session = requests.Session()

    def is_configured(self) -> bool:
        client_id = self.config.get("twitch", "client_id", default="")
        client_secret = self.config.get("twitch", "client_secret", default="")
        return bool(client_id and client_secret)

    def _client_id(self) -> str:
        return str(self.config.get("twitch", "client_id", default="") or "")

    def _client_secret(self) -> str:
        return str(self.config.get("twitch", "client_secret", default="") or "")

    def authenticate(self) -> str:
        """Client-credentials app access token."""
        if not self.is_configured():
            raise TwitchError(
                "Clés Twitch manquantes. Renseignez Client ID et Secret dans Paramètres."
            )
        resp = self._session.post(
            AUTH,
            params={
                "client_id": self._client_id(),
                "client_secret": self._client_secret(),
                "grant_type": "client_credentials",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise TwitchError(f"Auth Twitch échouée ({resp.status_code}): {resp.text}")
        data = resp.json()
        self._access_token = data["access_token"]
        return self._access_token

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            self.authenticate()
        return {
            "Client-ID": self._client_id(),
            "Authorization": f"Bearer {self._access_token}",
        }

    def _get(
        self, path: str, params: dict[str, Any] | list[tuple[str, str]]
    ) -> dict[str, Any]:
        resp = self._session.get(
            f"{HELIX}{path}", headers=self._headers(), params=params, timeout=30
        )
        if resp.status_code == 401:
            self.authenticate()
            resp = self._session.get(
                f"{HELIX}{path}", headers=self._headers(), params=params, timeout=30
            )
        if resp.status_code != 200:
            raise TwitchError(f"Twitch {path} → {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def get_user_by_login(self, login: str) -> Optional[dict[str, Any]]:
        data = self._get("/users", {"login": login.lower().strip()})
        users = data.get("data") or []
        return users[0] if users else None

    def get_users_by_logins(self, logins: list[str]) -> dict[str, dict[str, Any]]:
        """
        Resolve multiple logins → Helix user objects (keyed by lowercase login).

        Helix accepts up to 100 ``login`` query params per request.
        """
        cleaned = [str(x).lower().strip() for x in logins if str(x).strip()]
        cleaned = list(dict.fromkeys(cleaned))
        out: dict[str, dict[str, Any]] = {}
        for i in range(0, len(cleaned), 100):
            chunk = cleaned[i : i + 100]
            # requests encodes repeated keys as login=a&login=b
            data = self._get("/users", [("login", login) for login in chunk])
            for user in data.get("data") or []:
                key = str(user.get("login") or "").lower()
                if key:
                    out[key] = user
        return out

    def get_game_by_name(self, name: str) -> Optional[dict[str, Any]]:
        data = self._get("/games", {"name": name.strip()})
        games = data.get("data") or []
        return games[0] if games else None

    @staticmethod
    def _period_to_started_at(period: str) -> str:
        mapping = {"24h": 1, "7d": 7, "30d": 30}
        days = mapping.get(period, 7)
        started = datetime.now(timezone.utc) - timedelta(days=days)
        return started.strftime("%Y-%m-%dT%H:%M:%SZ")

    def search_clips(
        self,
        query: str,
        period: str = "7d",
        max_clips: int = 20,
        max_duration: float = 60.0,
        is_game: bool = False,
    ) -> list[Clip]:
        """
        Search clips by streamer login or game name, sorted by views desc.

        Twitch returns at most 100 clips per request — we paginate with the
        cursor until ``max_clips`` valid clips are collected (or no more pages).
        Filters out clips longer than ``max_duration``.
        """
        query = normalize_twitch_query(query)
        if not query:
            raise TwitchError("Indiquez un nom de streamer, un jeu, ou une URL Twitch.")

        target = max(1, min(int(max_clips), 500))
        base_params: dict[str, Any] = {
            "started_at": self._period_to_started_at(period),
        }

        game_name = ""
        broadcaster_name = ""

        if is_game:
            game = self.get_game_by_name(query)
            if not game:
                raise TwitchError(f"Jeu introuvable : {query}")
            base_params["game_id"] = game["id"]
            game_name = game.get("name", query)
        else:
            user = self.get_user_by_login(query)
            if not user:
                game = self.get_game_by_name(query)
                if game:
                    base_params["game_id"] = game["id"]
                    game_name = game.get("name", query)
                else:
                    raise TwitchError(f"Streamer ou jeu introuvable : {query}")
            else:
                base_params["broadcaster_id"] = user["id"]
                broadcaster_name = user.get("display_name") or user.get("login") or query

        clips: list[Clip] = []
        seen_ids: set[str] = set()
        cursor: Optional[str] = None
        # Fetch extra pages because duration filter drops some results
        max_pages = max(3, (target // 50) + 2)

        for _ in range(max_pages):
            page_size = min(100, max(target - len(clips) + 20, 20))
            params = dict(base_params)
            params["first"] = page_size
            if cursor:
                params["after"] = cursor

            data = self._get("/clips", params)
            batch = data.get("data") or []
            if not batch:
                break

            for item in batch:
                clip_id = item.get("id") or ""
                if not clip_id or clip_id in seen_ids:
                    continue
                duration = float(item.get("duration") or 0)
                if duration > max_duration:
                    continue
                created_raw = item.get("created_at")
                created_at = None
                if created_raw:
                    try:
                        created_at = datetime.fromisoformat(
                            created_raw.replace("Z", "+00:00")
                        )
                    except ValueError:
                        created_at = None
                seen_ids.add(clip_id)
                clips.append(
                    Clip(
                        id=clip_id,
                        title=item.get("title") or "Sans titre",
                        url=item.get("url") or "",
                        embed_url=item.get("embed_url") or "",
                        thumbnail_url=item.get("thumbnail_url") or "",
                        broadcaster_id=item.get("broadcaster_id") or "",
                        broadcaster_name=item.get("broadcaster_name")
                        or broadcaster_name,
                        creator_name=item.get("creator_name") or "",
                        game_id=item.get("game_id") or "",
                        game_name=game_name,
                        view_count=int(item.get("view_count") or 0),
                        duration=duration,
                        created_at=created_at,
                        language=item.get("language") or "en",
                    )
                )
                if len(clips) >= target:
                    break

            if len(clips) >= target:
                break
            cursor = (data.get("pagination") or {}).get("cursor")
            if not cursor:
                break

        clips.sort(key=lambda c: c.view_count, reverse=True)
        return clips[:target]
