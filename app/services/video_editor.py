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
        elif layout == LayoutType.FILL_HEIGHT:
            # Full-frame cover: video fills entire 9:16 height, no cam, no bars
            video_graph = (
                f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},setsar=1,fps={FPS},format=yuv420p"
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
    def _cover_center(w: int, h: int) -> str:
        """
        Scale-to-cover then crop the *center* of the frame into w×h.
        Keeps the middle of gameplay (crosshair / action) in the panel.
        """
        return (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}:(iw-ow)/2:(ih-oh)/2"
        )

    def _facecam_graph(self, region: FacecamRegion | None) -> str:
        """
        L-shape Shorts layout:
        - Compact cam panel top-left
        - Full-frame gameplay cover-fills the 9:16 canvas (center crop)
        """
        r = (region or FacecamRegion()).clamped()
        # Prefer a smaller cam by default for this style
        cam_w = int(round(W * min(r.width_ratio, 0.48)))
        cam_h = int(round(H * min(r.top_ratio, 0.28)))
        cam_w -= cam_w % 2
        cam_h -= cam_h % 2
        cam_w = max(280, min(cam_w, W - 2))
        cam_h = max(200, min(cam_h, H - 2))

        cam_crop = self._cam_crop_expr(r)
        cover = self._cover_center(W, H)
        return (
            f"[0:v]split=2[cam][game];"
            # Full source → center cover (gameplay middle stays in frame)
            f"[game]{cover},setsar=1,fps={FPS},format=yuv420p[bg];"
            f"[cam]{cam_crop},"
            f"{self._cover_center(cam_w, cam_h)},"
            f"setsar=1,format=yuv420p[pip];"
            f"[bg][pip]overlay=0:0"
        )

    def _facecam_quarter_graph(self, region: FacecamRegion | None) -> str:
        """
        Stacked Shorts: compact webcam on top, gameplay fills the rest.
        Gameplay uses a center cover-crop of the full source (no side-cut)
        so the middle of the action stays centered.
        """
        r = (region or FacecamRegion()).clamped()
        # Smaller cam strip (~18% height) — more room for gameplay
        cam_h = int(round(H * 0.18))
        cam_h -= cam_h % 2
        cam_h = max(200, min(cam_h, 420))
        game_h = H - cam_h
        game_h -= game_h % 2
        if cam_h + game_h != H:
            game_h = H - cam_h

        cam_crop = self._cam_crop_expr(r)
        return (
            f"[0:v]split=2[cam][game];"
            # Cam: fill the top strip completely (no black bars)
            f"[cam]{cam_crop},"
            f"{self._cover_center(W, cam_h)},"
            f"setsar=1,fps={FPS},format=yuv420p[top];"
            # Game: full frame, center cover into the tall bottom panel
            f"[game]{self._cover_center(W, game_h)},"
            f"setsar=1,fps={FPS},format=yuv420p[bot];"
            f"[top][bot]vstack=inputs=2,setsar=1,format=yuv420p"
        )
