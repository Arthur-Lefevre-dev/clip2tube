"""Title / description template rendering."""

from __future__ import annotations


def render_template(
    template: str,
    *,
    streamer: str = "",
    jeu: str = "",
    titre_clip: str = "",
    hashtags: str = "",
) -> str:
    """Replace ``{streamer}``, ``{jeu}``, ``{titre_clip}``, ``{hashtags}``."""
    return (
        template.replace("{streamer}", streamer)
        .replace("{jeu}", jeu)
        .replace("{titre_clip}", titre_clip)
        .replace("{hashtags}", hashtags)
    )


def ensure_shorts_hashtag(title: str) -> str:
    """Append #Shorts if missing (YouTube Shorts discovery)."""
    if "#shorts" in title.lower():
        return title
    return f"{title} #Shorts".strip()
