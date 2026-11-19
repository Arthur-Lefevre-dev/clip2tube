"""Online update check via GitHub Releases."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import requests

from app import __version__

DEFAULT_GITHUB_REPO = "Arthur-Lefevre-dev/clip2tube"
USER_AGENT = f"Clip2Tube/{__version__} (+https://github.com/{DEFAULT_GITHUB_REPO})"


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str
    available: bool
    release_url: str = ""
    download_url: str = ""
    asset_name: str = ""
    notes: str = ""
    error: str = ""


def normalize_version(raw: str) -> str:
    """Strip leading 'v' / spaces: 'v1.2.0' -> '1.2.0'."""
    text = (raw or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    return text.strip()


def version_tuple(raw: str) -> tuple[int, ...]:
    """Parse a semver-ish string into comparable ints (non-digits ignored)."""
    parts = re.split(r"[^\d]+", normalize_version(raw))
    nums = [int(p) for p in parts if p.isdigit()]
    return tuple(nums) if nums else (0,)


def is_newer(latest: str, current: str) -> bool:
    return version_tuple(latest) > version_tuple(current)


def _pick_asset(assets: list[dict]) -> tuple[str, str]:
    """Prefer Clip2Tube-Portable.zip, else first .zip."""
    if not assets:
        return "", ""
    preferred = []
    zips = []
    for asset in assets:
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if not url:
            continue
        lower = name.lower()
        if "portable" in lower and lower.endswith(".zip"):
            preferred.append((name, url))
        elif lower.endswith(".zip"):
            zips.append((name, url))
    if preferred:
        return preferred[0]
    if zips:
        return zips[0]
    first = assets[0]
    return str(first.get("name") or ""), str(first.get("browser_download_url") or "")


def check_for_updates(
    current_version: str = __version__,
    github_repo: str = DEFAULT_GITHUB_REPO,
    timeout: float = 12.0,
) -> UpdateInfo:
    """
    Query GitHub ``/releases/latest`` and compare tags to ``current_version``.

    The repo must publish a GitHub Release whose tag is the version
    (e.g. ``v1.0.1``) and ideally attach ``Clip2Tube-Portable.zip``.
    """
    current = normalize_version(current_version)
    repo = (github_repo or DEFAULT_GITHUB_REPO).strip().strip("/")
    if not repo or "/" not in repo:
        return UpdateInfo(
            current_version=current,
            latest_version=current,
            available=False,
            error="Dépôt GitHub invalide (attendu: owner/repo).",
        )

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        resp = requests.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT,
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return UpdateInfo(
            current_version=current,
            latest_version=current,
            available=False,
            error=f"Impossible de joindre GitHub : {exc}",
        )

    if resp.status_code == 404:
        return UpdateInfo(
            current_version=current,
            latest_version=current,
            available=False,
            error=(
                "Aucune release GitHub trouvée. "
                "Publiez une release (tag vX.Y.Z) sur le dépôt."
            ),
        )
    if resp.status_code != 200:
        return UpdateInfo(
            current_version=current,
            latest_version=current,
            available=False,
            error=f"GitHub a répondu {resp.status_code}.",
        )

    try:
        data = resp.json()
    except ValueError:
        return UpdateInfo(
            current_version=current,
            latest_version=current,
            available=False,
            error="Réponse GitHub illisible.",
        )

    tag = normalize_version(str(data.get("tag_name") or data.get("name") or ""))
    if not tag:
        return UpdateInfo(
            current_version=current,
            latest_version=current,
            available=False,
            error="La dernière release n’a pas de numéro de version.",
        )

    asset_name, download_url = _pick_asset(list(data.get("assets") or []))
    notes = str(data.get("body") or "").strip()
    release_url = str(data.get("html_url") or f"https://github.com/{repo}/releases/latest")

    return UpdateInfo(
        current_version=current,
        latest_version=tag,
        available=is_newer(tag, current),
        release_url=release_url,
        download_url=download_url,
        asset_name=asset_name,
        notes=notes,
        error="",
    )


def open_update_page(info: UpdateInfo) -> bool:
    """Open the release page (or asset URL) in the default browser."""
    import webbrowser

    target = info.download_url or info.release_url
    if not target:
        return False
    webbrowser.open(target)
    return True
