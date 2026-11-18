"""Local token encryption (Fernet, key stored under data/)."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.utils.paths import get_data_dir, ensure_dirs


def _key_path() -> Path:
    return get_data_dir() / ".secret.key"


def _load_or_create_key() -> bytes:
    """Derive / load a Fernet key unique to this install."""
    ensure_dirs()
    path = _key_path()
    if path.exists():
        return path.read_bytes()
    # Machine-local random key
    key = Fernet.generate_key()
    path.write_bytes(key)
    try:
        # Best-effort hide on Windows
        import ctypes

        FILE_ATTRIBUTE_HIDDEN = 0x02
        ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        pass
    return key


def encrypt_text(plain: str) -> bytes:
    """Encrypt a UTF-8 string; returns raw Fernet token bytes."""
    f = Fernet(_load_or_create_key())
    return f.encrypt(plain.encode("utf-8"))


def decrypt_text(token: bytes) -> str:
    """Decrypt Fernet token bytes back to a UTF-8 string."""
    if not token:
        return ""
    f = Fernet(_load_or_create_key())
    try:
        return f.decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Cannot decrypt token — key may have changed") from exc


def fingerprint(value: str) -> str:
    """Non-reversible short fingerprint for logs (never log secrets)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
