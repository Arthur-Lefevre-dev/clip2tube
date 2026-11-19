"""FFmpeg-based vertical video editor (3 layouts, 1080x1920 @ 30fps)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from app.models import LayoutType
from app.models.region import FacecamRegion
from app.utils.ffmpeg import find_ffmpeg, run_ffmpeg

ProgressCallback = Callable[[str], None]

W, H, FPS = 1080, 1920, 30


class VideoEditorError(Exception):
    pass


def _escape_drawtext(text: str) -> str:
    """Escape text for FFmpeg drawtext filter."""
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "%%")
        .replace("\n", " ")
    )


class VideoEditorService:
    """Render a 1080x1920 vertical video from a source clip."""

    def __init__(self, ffmpeg_path: str = "") -> None:
        self.ffmpeg_path = ffmpeg_path

    def render(
        self,
        source: Path,
        output: Path,
        layout: LayoutType,
        title: str = "",
        streamer: str = "",
        title_font: str = "Arial",
        title_color: str = "white",
        music_path: Path | None = None,
        music_volume: float = 0.15,
        facecam_region: FacecamRegion | None = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Path:
        binary = find_ffmpeg(self.ffmpeg_path)
        if binary is None:
            raise VideoEditorError(
                "FFmpeg introuvable. Configurez le chemin dans Paramètres."
            )

        output.parent.mkdir(parents=True, exist_ok=True)
        if on_progress:
            on_progress(f"Rendu layout {layout.value}…")

        title_e = _escape_drawtext(title[:80])
        streamer_e = _escape_drawtext(streamer[:40])
        color = title_color.lstrip("#")
        color = f"0x{color}" if len(color) == 6 else "white"

        draw_parts: list[str] = []
        if title_e:
            draw_parts.append(
                f"drawtext=text='{title_e}':font='{title_font}':fontsize=52:"
                f"fontcolor={color}:borderw=3:bordercolor=black@0.8:"
                f"x=(w-text_w)/2:y=60"
            )
        if streamer_e:
            draw_parts.append(
                f"drawtext=text='@{streamer_e}':font='{title_font}':fontsize=36:"
                f"fontcolor=white:borderw=2:bordercolor=black@0.8:"
                f"x=(w-text_w)/2:y=h-100"
            )
        draw = ",".join(draw_parts)

        if layout == LayoutType.BLUR_CENTER:
            # Blur fills canvas; gameplay fits width, centered (blur above/below — not black)
            video_graph = (
                f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},gblur=sigma=25,setsar=1[bg];"
                f"[0:v]scale={W}:-2:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={FPS},format=yuv420p"
            )
        elif layout == LayoutType.FACECAM_SPLIT:
            video_graph = self._facecam_graph(facecam_region)
        elif layout == LayoutType.FACECAM_QUARTER:
            video_graph = self._facecam_quarter_graph(facecam_region)
        else:
            # Classic letterbox — only layout that keeps intentional bars
            video_graph = (
                f"[0:v]scale={W}:-2:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fps={FPS},format=yuv420p,setsar=1"
            )

        if draw:
            video_graph = f"{video_graph}[base];[base]{draw}[vout]"
        else:
            video_graph = f"{video_graph}[vout]"

        args: list[str] = ["-i", str(source)]
        has_music = bool(music_path and music_path.exists())
        if has_music:
            vol = max(0.0, min(float(music_volume), 1.0))
            args += ["-stream_loop", "-1", "-i", str(music_path)]
            filter_complex = (
                f"{video_graph};"
                f"[0:a]aformat=sample_fmts=fltp:channel_layouts=stereo,volume=1.0[a0];"
                f"[1:a]aformat=sample_fmts=fltp:channel_layouts=stereo,volume={vol}[a1];"
                f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            args += [
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
            ]
        else:
            filter_complex = video_graph
            args += [
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-map",
                "0:a?",
            ]

        args += [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-r",
            str(FPS),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output),
        ]

        result = run_ffmpeg(args, ffmpeg_path=binary, timeout=600)
        if result.returncode != 0 or not output.exists():
            err = (result.stderr or result.stdout or "")[-1000:]
            raise VideoEditorError(f"FFmpeg a échoué:\n{err}")

        if on_progress:
            on_progress("Rendu vidéo terminé.")
        return output

    @staticmethod
    def _cam_crop_expr(r: FacecamRegion) -> str:
        return f"crop=iw*{r.w:.6f}:ih*{r.h:.6f}:iw*{r.x:.6f}:ih*{r.y:.6f}"

    @staticmethod
    def _game_crop_expr(r: FacecamRegion) -> str:
        """
        Crop the gameplay area of the Twitch frame (outside the webcam box)
        so the game can fill its panel without leftover black.
        """
        # Cam on the right → take everything to the left of the cam
        if r.x >= 0.40:
            gw = max(0.40, min(r.x + 0.02, 0.95))
            return f"crop=iw*{gw:.6f}:ih:0:0"
        # Cam on the left → take everything to the right of the cam
        right = r.x + r.w
        if right <= 0.60:
            gx = max(0.0, right - 0.02)
            gw = max(0.40, 1.0 - gx)
            return f"crop=iw*{gw:.6f}:ih:iw*{gx:.6f}:0"
        # Overlapping center — full frame, then cover-scale
        return "null"

    def _facecam_graph(self, region: FacecamRegion | None) -> str:
        """
        L-shape Shorts layout:
        - Cam panel top-left
        - Gameplay cover-fills the whole 9:16 canvas underneath (no black bars)
        """
        r = (region or FacecamRegion()).clamped()
        cam_w = int(round(W * r.width_ratio))
        cam_h = int(round(H * r.top_ratio))
        cam_w -= cam_w % 2
        cam_h -= cam_h % 2
        cam_w = max(320, min(cam_w, W - 2))
        cam_h = max(240, min(cam_h, H - 2))

        cam_crop = self._cam_crop_expr(r)
        game_crop = self._game_crop_expr(r)
        game_prep = f"{game_crop}," if game_crop != "null" else ""
        return (
            f"[0:v]split=2[cam][game];"
            f"[game]{game_prep}"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fps={FPS},format=yuv420p[bg];"
            f"[cam]{cam_crop},"
            f"scale={cam_w}:{cam_h}:force_original_aspect_ratio=increase,"
            f"crop={cam_w}:{cam_h},setsar=1,format=yuv420p[pip];"
            f"[bg][pip]overlay=0:0"
        )

    def _facecam_quarter_graph(self, region: FacecamRegion | None) -> str:
        """
        Stacked Shorts: webcam top 1/4, gameplay bottom 3/4.
        Game cover-fills its panel (no letterbox / black bars).
        """
        r = (region or FacecamRegion()).clamped()
        cam_h = H // 4
        game_h = H - cam_h
        cam_h -= cam_h % 2
        game_h = H - cam_h
        game_h -= game_h % 2
        # Keep exact canvas height
        if cam_h + game_h != H:
            game_h = H - cam_h

        cam_crop = self._cam_crop_expr(r)
        game_crop = self._game_crop_expr(r)
        game_prep = f"{game_crop}," if game_crop != "null" else ""
        return (
            f"[0:v]split=2[cam][game];"
            f"[cam]{cam_crop},"
            f"scale={W}:{cam_h}:force_original_aspect_ratio=increase,"
            f"crop={W}:{cam_h},setsar=1,fps={FPS},format=yuv420p[top];"
            f"[game]{game_prep}"
            f"scale={W}:{game_h}:force_original_aspect_ratio=increase,"
            f"crop={W}:{game_h},setsar=1,fps={FPS},format=yuv420p[bot];"
            f"[top][bot]vstack=inputs=2,setsar=1,format=yuv420p"
        )
