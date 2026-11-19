"""Custom clip list row — thumbnail, title, meta with clear spacing."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QPainterPath, QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models import Clip

THUMB_W = 168
THUMB_H = 94


class ClipRowWidget(QWidget):
    """One selectable clip row for the search results list."""

    toggled = Signal(bool)

    def __init__(self, clip: Clip, parent=None) -> None:
        super().__init__(parent)
        self.clip = clip
        self.setObjectName("ClipRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(124)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 14, 18, 14)
        root.setSpacing(18)

        self.check = QCheckBox()
        self.check.setObjectName("ClipCheck")
        self.check.toggled.connect(self.toggled.emit)
        root.addWidget(self.check, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Thumbnail with duration badge overlay
        self._thumb_wrap = QWidget()
        self._thumb_wrap.setFixedSize(THUMB_W, THUMB_H)
        self._thumb_wrap.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.thumb = QLabel(self._thumb_wrap)
        self.thumb.setObjectName("ClipThumb")
        self.thumb.setGeometry(0, 0, THUMB_W, THUMB_H)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setText("…")

        self.duration = QLabel(clip.duration_label, self._thumb_wrap)
        self.duration.setObjectName("ClipDuration")
        self.duration.adjustSize()
        self._place_duration()
        self.duration.raise_()
        root.addWidget(self._thumb_wrap, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Text column
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 6, 0, 6)
        text_col.setSpacing(10)

        self.title = QLabel(clip.title or "(sans titre)")
        self.title.setObjectName("ClipTitle")
        self.title.setWordWrap(True)
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_col.addWidget(self.title)

        meta = QHBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(0)

        created = (
            clip.created_at.strftime("%d/%m/%Y  %H:%M") if clip.created_at else "—"
        )
        parts = [
            ("ClipStreamer", clip.broadcaster_name or "—"),
            ("ClipMeta", f"{clip.views_label} vues"),
            ("ClipMeta", created),
        ]
        for i, (obj, text) in enumerate(parts):
            if i:
                sep = QLabel("·")
                sep.setObjectName("ClipSep")
                sep.setContentsMargins(10, 0, 10, 0)
                sep.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
                )
                meta.addWidget(sep)
            lab = QLabel(text)
            lab.setObjectName(obj)
            lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            meta.addWidget(lab)
        meta.addStretch(1)
        text_col.addLayout(meta)
        text_col.addStretch(1)
        root.addLayout(text_col, stretch=1)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(640, 124)

    def _place_duration(self) -> None:
        self.duration.adjustSize()
        hint = self.duration.sizeHint()
        self.duration.setGeometry(
            THUMB_W - hint.width() - 8,
            THUMB_H - hint.height() - 8,
            hint.width(),
            hint.height(),
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._place_duration()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            # Checkbox handles its own clicks; anywhere else on the row toggles.
            child = self.childAt(event.position().toPoint())
            on_check = child is self.check or (
                child is not None and self.check.isAncestorOf(child)
            )
            if not on_check:
                self.check.toggle()
                event.accept()
                return
        super().mousePressEvent(event)

    def is_checked(self) -> bool:
        return self.check.isChecked()

    def set_checked(self, checked: bool) -> None:
        self.check.setChecked(checked)

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            THUMB_W,
            THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Center-crop to exact size
        x = max(0, (scaled.width() - THUMB_W) // 2)
        y = max(0, (scaled.height() - THUMB_H) // 2)
        cropped = scaled.copy(x, y, THUMB_W, THUMB_H)

        rounded = QPixmap(THUMB_W, THUMB_H)
        rounded.fill(QColor(0, 0, 0, 0))
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, THUMB_W, THUMB_H, 10, 10)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self.thumb.setPixmap(rounded)
        self.thumb.setText("")
