"""Normalized crop region for facecam selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FacecamRegion:
    """
    Facecam rectangle in normalized *source* coordinates (0.0 – 1.0).

    ``x``, ``y``, ``w``, ``h`` = crop of the webcam inside the Twitch clip.

    Output placement (9:16 canvas) — L-shape layout:
    - Cam sits top-left covering ``width_ratio`` × ``top_ratio`` of the frame
    - Gameplay fills the rest (right of cam + full bottom)
    """

    x: float = 0.70
    y: float = 0.05
    w: float = 0.28
    h: float = 0.40
    # Output panel size (matches the red zone on the user's sketch)
    top_ratio: float = 0.33  # cam height ~1/3
    width_ratio: float = 0.66  # cam width ~2/3

    def clamped(self) -> FacecamRegion:
        """Return a copy with values clamped to a valid rectangle."""
        x = max(0.0, min(self.x, 0.95))
        y = max(0.0, min(self.y, 0.95))
        w = max(0.05, min(self.w, 1.0 - x))
        h = max(0.05, min(self.h, 1.0 - y))
        top_ratio = max(0.22, min(float(self.top_ratio), 0.50))
        width_ratio = max(0.40, min(float(self.width_ratio), 0.85))
        return FacecamRegion(
            x=x, y=y, w=w, h=h, top_ratio=top_ratio, width_ratio=width_ratio
        )

    def as_tuple(self) -> tuple[float, float, float, float]:
        r = self.clamped()
        return (r.x, r.y, r.w, r.h)

    def to_dict(self) -> dict[str, float]:
        r = self.clamped()
        return {
            "x": r.x,
            "y": r.y,
            "w": r.w,
            "h": r.h,
            "top_ratio": r.top_ratio,
            "width_ratio": r.width_ratio,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> FacecamRegion:
        if not data:
            return cls()
        return cls(
            x=float(data.get("x", 0.70)),
            y=float(data.get("y", 0.05)),
            w=float(data.get("w", 0.28)),
            h=float(data.get("h", 0.40)),
            top_ratio=float(data.get("top_ratio", 0.33)),
            width_ratio=float(data.get("width_ratio", 0.66)),
        ).clamped()

    def label(self) -> str:
        r = self.clamped()
        return f"{r.x:.0%}×{r.y:.0%} · {r.w:.0%}×{r.h:.0%}"
