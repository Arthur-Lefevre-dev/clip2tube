"""Shared page chrome: title, subtitle, placeholder body."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class BasePage(QWidget):
    """Reusable shell for navigation pages."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        placeholder_title: str,
        placeholder_body: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._build(title, subtitle, placeholder_title, placeholder_body)

    def _build(
        self,
        title: str,
        subtitle: str,
        placeholder_title: str,
        placeholder_body: str,
    ) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        root.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
        root.addWidget(subtitle_label)

        card = QFrame()
        card.setObjectName("PlaceholderCard")
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(8)

        card_title = QLabel(placeholder_title)
        card_title.setObjectName("PlaceholderTitle")
        card_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(card_title)

        card_body = QLabel(placeholder_body)
        card_body.setObjectName("PlaceholderBody")
        card_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_body.setWordWrap(True)
        card_layout.addWidget(card_body)

        root.addWidget(card, stretch=1)
