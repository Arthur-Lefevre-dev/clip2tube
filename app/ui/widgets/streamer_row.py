"""Streamer list row — avatar + display name + login."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QPainterPath, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

AVATAR = 48


class StreamerRowWidget(QWidget):
    """One followed-streamer row with profile image."""

    clicked = Signal()

    def __init__(
        self,
        login: str,
        display_name: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.login = login
        self.setObjectName("StreamerRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(68)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_selected(False)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(12)

        self.avatar = QLabel()
        self.avatar.setObjectName("StreamerAvatar")
        self.avatar.setFixedSize(AVATAR, AVATAR)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setText((display_name or login)[:1].upper())
        root.addWidget(self.avatar)

        text = QVBoxLayout()
        text.setContentsMargins(0, 2, 0, 2)
        text.setSpacing(2)

        self.name_label = QLabel(display_name or login)
        self.name_label.setObjectName("StreamerDisplayName")
        self.name_label.setWordWrap(False)
        text.addWidget(self.name_label)

        self.login_label = QLabel(f"twitch.tv/{login}")
        self.login_label.setObjectName("StreamerLogin")
        text.addWidget(self.login_label)
        root.addLayout(text, stretch=1)

    def sizeHint(self) -> QSize:
        return QSize(320, 68)

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

    def set_profile(self, display_name: str) -> None:
        if display_name:
            self.name_label.setText(display_name)
            if not self.avatar.pixmap() or self.avatar.pixmap().isNull():
                self.avatar.setText(display_name[:1].upper())

    def set_avatar(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            AVATAR,
            AVATAR,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - AVATAR) // 2)
        y = max(0, (scaled.height() - AVATAR) // 2)
        cropped = scaled.copy(x, y, AVATAR, AVATAR)

        rounded = QPixmap(AVATAR, AVATAR)
        rounded.fill(QColor(0, 0, 0, 0))
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, AVATAR, AVATAR)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self.avatar.setPixmap(rounded)
        self.avatar.setText("")
