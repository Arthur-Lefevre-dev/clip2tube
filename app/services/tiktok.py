"""TikTok Content Posting API (or export fallback for manual upload)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4
from urllib.parse import urlencode
import webbrowser

import requests

from app.db import Database
from app.models import Account, Platform
from app.utils.config import AppConfig
from app.utils.crypto import decrypt_text, encrypt_text
from app.utils.paths import get_app_root, get_data_dir, ensure_dirs

TOKEN_FILE = "tiktok_token.enc"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


class TikTokError(Exception):
    pass


class TikTokService:
    """Publish to TikTok when API keys allow it; otherwise export the file."""

    def __init__(self, config: AppConfig, database: Database) -> None:
        self.config = config
        self.database = database

    def is_configured(self) -> bool:
        return bool(
            self.config.get("tiktok", "client_key", default="")
            and self.config.get("tiktok", "client_secret", default="")
        )

    def is_api_available(self) -> bool:
        """
        TikTok Content Posting requires approved app access.
        We treat missing keys / missing token as export-only mode.
        """
        return self.is_configured()

    def is_connected(self) -> bool:
        account = self.database.get_account(Platform.TIKTOK)
        return account is not None and bool(account.token_encrypted)

    def disconnect(self) -> None:
        self.database.delete_account(Platform.TIKTOK)
        path = get_data_dir() / TOKEN_FILE
        if path.exists():
            path.unlink()

    def connect(self) -> str:
        """
        Open TikTok OAuth in the browser.

        Full redirect handling needs a registered redirect URI in the TikTok
        developer portal. If the API is not approved, raise a clear message
        and keep export mode available.
        """
        if not self.is_configured():
            raise TikTokError(
                "Clés TikTok manquantes. Sans API approuvée, utilisez le mode export."
            )

        client_key = self.config.get("tiktok", "client_key")
        # User must paste the auth code from redirect — store a pending flag
        params = {
            "client_key": client_key,
            "scope": "user.info.basic,video.upload,video.publish",
            "response_type": "code",
            "redirect_uri": "https://localhost/callback",
            "state": str(uuid4()),
        }
        url = f"{AUTH_URL}?{urlencode(params)}"
        webbrowser.open(url)
        raise TikTokError(
            "Navigateur ouvert pour TikTok OAuth.\n"
            "Si votre app n'est pas encore approuvée Content Posting, "
            "utilisez le mode EXPORT (dossier prêt pour upload manuel).\n"
            "Sinon, collez le code d'autorisation via complete_oauth(code)."
        )

    def complete_oauth(self, code: str) -> str:
        """Exchange auth code for token and store encrypted."""
        if not code.strip():
            raise TikTokError("Code d'autorisation vide.")
        resp = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": self.config.get("tiktok", "client_key"),
                "client_secret": self.config.get("tiktok", "client_secret"),
                "code": code.strip(),
                "grant_type": "authorization_code",
                "redirect_uri": "https://localhost/callback",
            },
            timeout=30,
        )
        data = resp.json()
        if "access_token" not in data and "data" not in data:
            raise TikTokError(f"OAuth TikTok échoué: {data}")
        payload = data.get("data") or data
        encrypted = encrypt_text(json.dumps(payload))
        (get_data_dir() / TOKEN_FILE).write_bytes(encrypted)

        open_id = str(payload.get("open_id") or uuid4())
        account = Account(
            id=open_id,
            platform=Platform.TIKTOK,
            display_name=f"TikTok {open_id[:8]}",
            channel_id=open_id,
            token_encrypted=encrypted,
            connected_at=datetime.utcnow(),
            is_active=True,
        )
        self.database.upsert_account(account)
        return account.display_name

    def _access_token(self) -> str:
        account = self.database.get_account(Platform.TIKTOK)
        raw = account.token_encrypted if account else b""
        if not raw:
            path = get_data_dir() / TOKEN_FILE
            if path.exists():
                raw = path.read_bytes()
        if not raw:
            raise TikTokError("Compte TikTok non connecté.")
        data = json.loads(decrypt_text(raw))
        token = data.get("access_token")
        if not token:
            raise TikTokError("Token TikTok invalide.")
        return token

    def export_for_manual_upload(
        self, video_path: Path, caption: str, export_dir: Optional[Path] = None
    ) -> Path:
        """Copy video + caption sidecar into an export folder."""
        ensure_dirs()
        dest_root = export_dir or (
            Path(self.config.get("output_dir", default="output") or "output")
        )
        if not dest_root.is_absolute():
            dest_root = get_app_root() / dest_root
        folder = dest_root / "tiktok_export"
        folder.mkdir(parents=True, exist_ok=True)

        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest = folder / f"{stamp}_{video_path.name}"
        shutil.copy2(video_path, dest)
        (dest.with_suffix(".txt")).write_text(caption, encoding="utf-8")
        return dest

    def upload_or_export(
        self,
        video_path: Path,
        caption: str,
        export_dir: Optional[Path] = None,
        force_export: bool = False,
    ) -> str:
        """
        Try Content Posting API; fall back to export folder.

        Returns publish id or export path as string.
        """
        if force_export or not self.is_connected():
            path = self.export_for_manual_upload(video_path, caption, export_dir)
            return str(path)

        # Minimal direct-post attempt (requires approved TikTok app)
        try:
            token = self._access_token()
            init = requests.post(
                "https://open.tiktokapis.com/v2/post/publish/video/init/",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                json={
                    "post_info": {
                        "title": caption[:150],
                        "privacy_level": "SELF_ONLY",
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": video_path.stat().st_size,
                        "chunk_size": video_path.stat().st_size,
                        "total_chunk_count": 1,
                    },
                },
                timeout=60,
            )
            payload = init.json()
            error = (payload.get("error") or {}).get("code")
            if error and error != "ok":
                path = self.export_for_manual_upload(video_path, caption, export_dir)
                return f"export:{path}"

            data = payload.get("data") or {}
            upload_url = data.get("upload_url")
            publish_id = data.get("publish_id") or ""
            if upload_url:
                with video_path.open("rb") as fh:
                    put = requests.put(
                        upload_url,
                        headers={
                            "Content-Type": "video/mp4",
                            "Content-Length": str(video_path.stat().st_size),
                            "Content-Range": f"bytes 0-{video_path.stat().st_size - 1}/{video_path.stat().st_size}",
                        },
                        data=fh,
                        timeout=300,
                    )
                    if put.status_code >= 400:
                        path = self.export_for_manual_upload(
                            video_path, caption, export_dir
                        )
                        return f"export:{path}"
            return publish_id or "tiktok_ok"
        except Exception:
            path = self.export_for_manual_upload(video_path, caption, export_dir)
            return f"export:{path}"
