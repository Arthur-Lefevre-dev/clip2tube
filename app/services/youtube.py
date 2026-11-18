"""YouTube Data API v3 publishing (OAuth 2.0)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.db import Database
from app.models import Account, Platform
from app.utils.config import AppConfig
from app.utils.crypto import decrypt_text, encrypt_text
from app.utils.paths import get_data_dir

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "youtube_token.enc"


class YouTubeError(Exception):
    pass


class YouTubeService:
    """Authenticate and upload Shorts to YouTube."""

    def __init__(self, config: AppConfig, database: Database) -> None:
        self.config = config
        self.database = database

    def is_configured(self) -> bool:
        return bool(
            self.config.get("google", "client_id", default="")
            and self.config.get("google", "client_secret", default="")
        )

    def is_connected(self) -> bool:
        account = self.database.get_account(Platform.YOUTUBE)
        return account is not None and bool(account.token_encrypted)

    def disconnect(self) -> None:
        self.database.delete_account(Platform.YOUTUBE)
        path = get_data_dir() / TOKEN_FILE
        if path.exists():
            path.unlink()

    def connect(self) -> str:
        """
        Run installed-app OAuth flow in the browser.
        Returns the channel title / display name.
        """
        if not self.is_configured():
            raise YouTubeError(
                "Client ID / Secret Google manquants dans Paramètres."
            )
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise YouTubeError(
                "Packages Google manquants. "
                "pip install google-api-python-client google-auth-oauthlib"
            ) from exc

        client_config = {
            "installed": {
                "client_id": self.config.get("google", "client_id"),
                "client_secret": self.config.get("google", "client_secret"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)

        token_json = creds.to_json()
        encrypted = encrypt_text(token_json)
        (get_data_dir() / TOKEN_FILE).write_bytes(encrypted)

        youtube = build("youtube", "v3", credentials=creds)
        me = youtube.channels().list(part="snippet", mine=True).execute()
        items = me.get("items") or []
        title = "YouTube"
        channel_id = ""
        if items:
            title = items[0]["snippet"]["title"]
            channel_id = items[0]["id"]

        account = Account(
            id=str(uuid4()),
            platform=Platform.YOUTUBE,
            display_name=title,
            channel_id=channel_id,
            token_encrypted=encrypted,
            connected_at=datetime.utcnow(),
            is_active=True,
        )
        self.database.upsert_account(account)
        return title

    def _credentials(self):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        account = self.database.get_account(Platform.YOUTUBE)
        raw = b""
        if account and account.token_encrypted:
            raw = account.token_encrypted
        else:
            path = get_data_dir() / TOKEN_FILE
            if path.exists():
                raw = path.read_bytes()
        if not raw:
            raise YouTubeError("Compte YouTube non connecté.")

        data = json.loads(decrypt_text(raw))
        creds = Credentials.from_authorized_user_info(data, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            encrypted = encrypt_text(creds.to_json())
            (get_data_dir() / TOKEN_FILE).write_bytes(encrypted)
            if account:
                account.token_encrypted = encrypted
                account.last_used_at = datetime.utcnow()
                self.database.upsert_account(account)
        return creds

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        scheduled_at: Optional[datetime] = None,
    ) -> str:
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise YouTubeError("google-api-python-client manquant") from exc

        if not video_path.exists():
            raise YouTubeError(f"Vidéo introuvable: {video_path}")

        creds = self._credentials()
        youtube = build("youtube", "v3", credentials=creds)

        body: dict = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "categoryId": "20",  # Gaming
            },
            "status": {
                "privacyStatus": "private" if scheduled_at else "public",
                "selfDeclaredMadeForKids": False,
            },
        }
        if scheduled_at:
            # YouTube expects RFC3339 UTC
            if scheduled_at.tzinfo is None:
                publish_at = scheduled_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            else:
                publish_at = scheduled_at.astimezone().strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z"
                )
            body["status"]["publishAt"] = publish_at
            body["status"]["privacyStatus"] = "private"

        media = MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            _status, response = request.next_chunk()
        video_id = response.get("id") or ""
        if not video_id:
            raise YouTubeError("Upload YouTube sans id vidéo.")
        return video_id
