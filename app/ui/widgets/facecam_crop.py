"""Interactive facecam region selector (drag a rectangle on a video frame)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.region import FacecamRegion
from app.utils.ffmpeg import find_ffmpeg, run_ffmpeg


def extract_frame(
    video_path: Path,
    output_image: Path,
    time_sec: float = 1.0,
    ffmpeg_path: str = "",
) -> Path:
    """Extract a single JPEG frame from a video with FFmpeg."""
    binary = find_ffmpeg(ffmpeg_path)
    if binary is None:
        raise FileNotFoundError("FFmpeg introuvable pour extraire une frame.")
    output_image.parent.mkdir(parents=True, exist_ok=True)
    result = run_ffmpeg(
        [
            "-ss",
            str(max(time_sec, 0)),
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_image),
        ],
        ffmpeg_path=binary,
        timeout=60,
    )
    if result.returncode != 0 or not output_image.exists():
        # Retry from start if seek failed
        result = run_ffmpeg(
            ["-i", str(video_path), "-frames:v", "1", "-q:v", "2", str(output_image)],
            ffmpeg_path=binary,
            timeout=60,
        )
    if not output_image.exists():
        raise RuntimeError("Impossible d'extraire une image du clip.")
    return output_image


class CropCanvas(QWidget):
    """Displays a frame and lets the user drag-select a rectangle."""

    region_changed = Signal(object)  # FacecamRegion

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self._pixmap = QPixmap()
        self._region = FacecamRegion()
        self._dragging = False
        self._origin = QPoint()
        self._current = QRect()
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_image(self, image_path: Path) -> None:
        img = QImage(str(image_path))
        if img.isNull():
            raise RuntimeError(f"Image illisible: {image_path}")
        self._pixmap = QPixmap.fromImage(img)
        self.update()

    def set_region(self, region: FacecamRegion) -> None:
        self._region = region.clamped()
        self.update()
        self.region_changed.emit(self._region)

    def region(self) -> FacecamRegion:
        return self._region.clamped()

    def _image_rect(self) -> QRect:
        """Letterboxed destination rect of the pixmap inside the widget."""
        if self._pixmap.isNull():
            return QRect()
        scaled = self._pixmap.size()
        scaled.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def _norm_from_widget(self, rect: QRect) -> FacecamRegion:
        ir = self._image_rect()
        if ir.width() <= 0 or ir.height() <= 0:
            return self._region
        inter = rect.intersected(ir)
        if inter.width() < 4 or inter.height() < 4:
            return self._region
        x = (inter.x() - ir.x()) / ir.width()
        y = (inter.y() - ir.y()) / ir.height()
        w = inter.width() / ir.width()
        h = inter.height() / ir.height()
        return FacecamRegion(x=x, y=y, w=w, h=h).clamped()

    def _widget_from_norm(self, region: FacecamRegion) -> QRect:
        ir = self._image_rect()
        r = region.clamped()
        return QRect(
            int(ir.x() + r.x * ir.width()),
            int(ir.y() + r.y * ir.height()),
            max(2, int(r.w * ir.width())),
            max(2, int(r.h * ir.height())),
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0f1115"))
        if self._pixmap.isNull():
            painter.setPen(QColor("#8b95a8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Aucune image")
            return

        ir = self._image_rect()
        painter.drawPixmap(ir, self._pixmap)

        # Dim outside selection
        sel = self._current if self._dragging and self._current.isValid() else self._widget_from_norm(self._region)
        overlay = QColor(0, 0, 0, 110)
        painter.fillRect(QRect(ir.topLeft(), QPoint(ir.right(), sel.top())), overlay)
        painter.fillRect(QRect(QPoint(ir.left(), sel.bottom() + 1), ir.bottomRight()), overlay)
        painter.fillRect(
            QRect(QPoint(ir.left(), sel.top()), QPoint(sel.left() - 1, sel.bottom())),
            overlay,
        )
        painter.fillRect(
            QRect(QPoint(sel.right() + 1, sel.top()), QPoint(ir.right(), sel.bottom())),
            overlay,
        )

        pen = QPen(QColor("#9146ff"), 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.drawRect(sel)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(sel.adjusted(6, 4, -4, -4), "Cam streamer")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._pixmap.isNull():
            return
        ir = self._image_rect()
        if not ir.contains(event.position().toPoint()):
            return
        self._dragging = True
        self._origin = event.position().toPoint()
        self._current = QRect(self._origin, self._origin)
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._dragging:
            return
        self._current = QRect(self._origin, event.position().toPoint()).normalized()
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if not self._dragging or event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = False
        self._current = QRect(self._origin, event.position().toPoint()).normalized()
        region = self._norm_from_widget(self._current)
        self.set_region(region)
        self._current = QRect()


class FacecamCropDialog(QDialog):
    """Modal dialog to pick the streamer webcam zone on a clip frame."""

    def __init__(
        self,
        frame_path: Path,
        initial: FacecamRegion | None = None,
        parent=None,
        title: str = "Zone cam streamer",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 560)
        self._result = (initial or FacecamRegion()).clamped()

        root = QVBoxLayout(self)
        hint = QLabel(
            "Cliquez-glissez sur la webcam du streamer. "
            "Cette zone ira en haut ; le gameplay remplira le bas."
        )
        hint.setWordWrap(True)
        hint.setObjectName("PageSubtitle")
        root.addWidget(hint)

        self.canvas = CropCanvas()
        self.canvas.set_image(frame_path)
        self.canvas.set_region(self._result)
        self.canvas.region_changed.connect(self._on_region)
        root.addWidget(self.canvas, stretch=1)

        row = QHBoxLayout()
        self.info = QLabel(self._result.label())
        self.info.setObjectName("PageSubtitle")
        row.addWidget(self.info)
        row.addStretch(1)

        preset_tr = QPushButton("Preset coin haut-droit")
        preset_tr.setObjectName("SecondaryButton")
        preset_tr.clicked.connect(
            lambda: self.canvas.set_region(FacecamRegion(0.72, 0.02, 0.26, 0.38))
        )
        preset_tl = QPushButton("Preset coin haut-gauche")
        preset_tl.setObjectName("SecondaryButton")
        preset_tl.clicked.connect(
            lambda: self.canvas.set_region(FacecamRegion(0.02, 0.02, 0.26, 0.38))
        )
        row.addWidget(preset_tl)
        row.addWidget(preset_tr)
        root.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_region(self, region: FacecamRegion) -> None:
        self._result = region
        self.info.setText(region.label())

    def selected_region(self) -> FacecamRegion:
        return self.canvas.region()

    @staticmethod
    def pick(
        frame_path: Path,
        initial: FacecamRegion | None = None,
        parent=None,
        title: str = "Zone cam streamer",
    ) -> FacecamRegion | None:
        dlg = FacecamCropDialog(
            frame_path, initial=initial, parent=parent, title=title
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.selected_region()
