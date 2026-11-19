"""Automatic subtitles via faster-whisper + FFmpeg ASS burn-in."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from app.utils.ffmpeg import find_ffmpeg, run_ffmpeg

ProgressCallback = Callable[[str], None]


class SubtitlesError(Exception):
    pass


def _ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_color(hex_color: str) -> str:
    """Convert #RRGGBB to ASS &H00BBGGRR."""
    c = hex_color.lstrip("#")
    if len(c) != 6:
        return "&H00FFFFFF"
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H00{b.upper()}{g.upper()}{r.upper()}"


class SubtitlesService:
    """Transcribe audio and burn word-by-word animated captions."""

    def __init__(self, ffmpeg_path: str = "") -> None:
        self.ffmpeg_path = ffmpeg_path

    def transcribe_and_burn(
        self,
        video_path: Path,
        output_path: Path,
        language: str = "auto",
        model_size: str = "small",
        font: str = "Arial",
        color: str = "#FFFFFF",
        use_gpu: bool = True,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Path:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SubtitlesError(
                "faster-whisper n'est pas installé. "
                "Lancez: pip install faster-whisper"
            ) from exc

        from app.utils.gpu import detect_gpu, prepare_rocm_env, resolve_whisper_device

        device, compute_type, reason = resolve_whisper_device(use_gpu=use_gpu)
        gpu = detect_gpu()
        if gpu.vendor == "amd" and device == "cuda":
            prepare_rocm_env()
        if on_progress:
            on_progress(f"Whisper : {reason}")
            backend = "ROCm" if gpu.vendor == "amd" and device == "cuda" else device
            on_progress(
                f"Chargement modèle ({model_size}) sur {backend}/{compute_type}…"
            )

        try:
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception as gpu_exc:
            # Fallback to CPU if GPU / ROCm init fails
            if on_progress:
                on_progress(
                    f"Échec GPU ({gpu_exc}) — bascule sur CPU…"
                )
            model = WhisperModel(model_size, device="cpu", compute_type="int8")

        if on_progress:
            on_progress("Transcription en cours…")

        lang = None if language in ("", "auto") else language
        segments, _info = model.transcribe(
            str(video_path),
            language=lang,
            word_timestamps=True,
            vad_filter=True,
        )

        words: list[tuple[float, float, str]] = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    text = (w.word or "").strip()
                    if text:
                        words.append((float(w.start), float(w.end), text))
            else:
                text = (segment.text or "").strip()
                if text:
                    words.append((float(segment.start), float(segment.end), text))

        if not words:
            if on_progress:
                on_progress("Aucun sous-titre détecté — copie sans burn-in.")
            output_path.write_bytes(video_path.read_bytes())
            return output_path

        ass_path = output_path.with_suffix(".ass")
        self._write_ass(ass_path, words, font=font, color=color)

        if on_progress:
            on_progress("Incrustation des sous-titres…")

        binary = find_ffmpeg(self.ffmpeg_path)
        if binary is None:
            raise SubtitlesError("FFmpeg introuvable pour brûler les sous-titres.")

        # Escape path for subtitles filter on Windows
        ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
        result = run_ffmpeg(
            [
                "-i",
                str(video_path),
                "-vf",
                f"ass='{ass_escaped}'",
                "-c:a",
                "copy",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                str(output_path),
            ],
            ffmpeg_path=binary,
            timeout=600,
        )
        if result.returncode != 0 or not output_path.exists():
            err = (result.stderr or "")[-600:]
            raise SubtitlesError(f"Burn-in sous-titres échoué:\n{err}")

        try:
            ass_path.unlink(missing_ok=True)
        except OSError:
            pass

        if on_progress:
            on_progress("Sous-titres terminés.")
        return output_path

    def _write_ass(
        self,
        path: Path,
        words: list[tuple[float, float, str]],
        font: str,
        color: str,
    ) -> None:
        primary = _ass_color(color)
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},72,{primary},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,2,40,40,520,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        # Group ~3 words per event for Shorts-style punchy captions
        i = 0
        while i < len(words):
            chunk = words[i : i + 3]
            start = chunk[0][0]
            end = max(w[1] for w in chunk)
            if end <= start:
                end = start + 0.35
            text = " ".join(w[2] for w in chunk)
            text = text.replace("{", "(").replace("}", ")")
            # Pop-in effect via {\fad}
            lines.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{{\\fad(80,80)}}{text}\n"
            )
            i += 3
        path.write_text("".join(lines), encoding="utf-8")
