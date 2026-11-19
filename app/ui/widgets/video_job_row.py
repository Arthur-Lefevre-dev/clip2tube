"""Job / video list row for « Mes vidéos »."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QPainterPath, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models import Job, JobStatus

THUMB_W = 54
THUMB_H = 96

_STATUS_FR: dict[str, str] = {
    JobStatus.PENDING.value: "En attente",
    JobStatus.DOWNLOADING.value: "Téléchargement",
    JobStatus.PROCESSING.value: "Montage",
    JobStatus.SUBTITLING.value: "Sous-titres",
    JobStatus.QUEUED.value: "Programmée",
    JobStatus.UPLOADING.value: "Publication…",
    JobStatus.PUBLISHED.value: "Publiée",
    JobStatus.ERROR.value: "Erreur",
    JobStatus.CANCELLED.value: "Annulée",
}


def status_label(status: JobStatus | str) -> str:
    value = status.value if isinstance(status, JobStatus) else str(status)
    return _STATUS_FR.get(value, value)


def status_kind(status: JobStatus | str) -> str:
    value = status.value if isinstance(status, JobStatus) else str(status)
    if value == JobStatus.PUBLISHED.value:
        return "ok"
    if value == JobStatus.ERROR.value:
        return "error"
    if value in {JobStatus.QUEUED.value, JobStatus.UPLOADING.value}:
        return "busy"
    if value in {
        JobStatus.PROCESSING.value,
        JobStatus.SUBTITLING.value,
        JobStatus.DOWNLOADING.value,
    }:
        return "busy"
    return "idle"


class VideoJobRow(QWidget):
    """One rendered / queued video card."""

    clicked = Signal()

    def __init__(self, job: Job, parent=None) -> None:
        super().__init__(parent)
        self.job_id = job.id
        self.setObjectName("VideoJobRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(112)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_selected(False)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(14)

        self.thumb = QLabel()
        self.thumb.setObjectName("VideoJobThumb")
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setText("▶")
        root.addWidget(self.thumb)

        col = QVBoxLayout()
        col.setContentsMargins(0, 2, 0, 2)
        col.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.title = QLabel(job.clip_title or "(sans titre)")
        self.title.setObjectName("VideoJobTitle")
        self.title.setWordWrap(True)
        top.addWidget(self.title, stretch=1)
        self.badge = QLabel(status_label(job.status))
        self.badge.setObjectName("VideoJobBadge")
        self._apply_badge(job.status)
        top.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignTop)
        col.addLayout(top)

        meta_bits = [job.streamer or "—"]
        if job.output_path and Path(job.output_path).exists():
            meta_bits.append("Fichier prêt")
        elif job.output_path:
            meta_bits.append("Fichier manquant")
        else:
            meta_bits.append("Pas encore rendue")
        if job.scheduled_at:
            meta_bits.append(job.scheduled_at.strftime("%d/%m/%Y %H:%M"))
        if job.youtube_video_id:
            meta_bits.append(f"YT {job.youtube_video_id}")

        self.meta = QLabel(" · ".join(meta_bits))
        self.meta.setObjectName("VideoJobMeta")
        self.meta.setWordWrap(True)
        col.addWidget(self.meta)

        err = (job.error_message or "").strip()
        self.error = QLabel(err[:120] if err else "")
        self.error.setObjectName("VideoJobError")
        self.error.setWordWrap(True)
        self.error.setVisible(bool(err))
        col.addWidget(self.error)

        col.addStretch(1)
        root.addLayout(col, stretch=1)

    def sizeHint(self) -> QSize:
        return QSize(480, 112)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            THUMB_W,
            THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - THUMB_W) // 2)
        y = max(0, (scaled.height() - THUMB_H) // 2)
        cropped = scaled.copy(x, y, THUMB_W, THUMB_H)
        rounded = QPixmap(THUMB_W, THUMB_H)
        rounded.fill(QColor(0, 0, 0, 0))
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, THUMB_W, THUMB_H, 8, 8)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self.thumb.setPixmap(rounded)
        self.thumb.setText("")

    def _apply_badge(self, status: JobStatus | str) -> None:
        kind = status_kind(status)
        self.badge.setProperty("kind", kind)
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
