"""Illustrated layout style picker."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QButtonGroup, QGridLayout, QToolButton, QWidget

from app.models import LayoutType
from app.utils.paths import get_asset_path


_LAYOUTS: list[tuple[str, str, str]] = [
    (
        LayoutType.BLUR_CENTER.value,
        "Fond flou\nJeu centré\n★ recommandé",
        "blur_center.png",
    ),
    (
        LayoutType.FACECAM_SPLIT.value,
        "Webcam\nCam en haut\nà gauche",
        "facecam_split.png",
    ),
    (
        LayoutType.FACECAM_QUARTER.value,
        "1/4 cam\n3/4 vidéo\nempilé",
        "facecam_quarter.png",
    ),
    (
        LayoutType.LETTERBOX.value,
        "Barres\nLetterbox\nclassique",
        "letterbox.png",
    ),
]


def _fallback_icon(kind: str) -> QPixmap:
    pix = QPixmap(96, 160)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#1a1e28"))
    p.setPen(QPen(QColor("#343b4d"), 2))
    p.drawRoundedRect(4, 4, 88, 152, 14, 14)
    if kind == LayoutType.BLUR_CENTER.value:
        p.setBrush(QColor("#3c3250"))
        p.drawRoundedRect(10, 10, 76, 140, 10, 10)
        p.setBrush(QColor("#7864a0"))
        p.drawRoundedRect(20, 48, 56, 64, 8, 8)
    elif kind == LayoutType.FACECAM_SPLIT.value:
        p.setBrush(QColor("#28465a"))
        p.drawRoundedRect(10, 10, 76, 140, 10, 10)
        p.setBrush(QColor("#e84d8a"))
        p.drawRoundedRect(14, 14, 36, 44, 8, 8)
    elif kind == LayoutType.FACECAM_QUARTER.value:
        p.setBrush(QColor("#e84d8a"))
        p.drawRoundedRect(10, 10, 76, 36, 6, 6)
        p.setBrush(QColor("#28465a"))
        p.drawRoundedRect(10, 52, 76, 98, 6, 6)
    else:
        p.setBrush(QColor("#0a0c10"))
        p.drawRect(10, 10, 76, 28)
        p.drawRect(10, 122, 76, 28)
        p.setBrush(QColor("#5a6e8c"))
        p.drawRoundedRect(12, 42, 72, 76, 4, 4)
    p.end()
    return pix


def _load_icon(value: str, icon_name: str) -> QIcon:
    path = get_asset_path("layouts", icon_name)
    if path.is_file():
        pix = QPixmap(str(path))
    else:
        pix = _fallback_icon(value)
    return QIcon(pix)


class LayoutPicker(QWidget):
    """Illustrated toggle buttons for vertical layout styles."""

    layout_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._value = LayoutType.BLUR_CENTER.value
        self._buttons: dict[str, QToolButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._build()

    def _build(self) -> None:
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)

        for i, (value, label, icon_name) in enumerate(_LAYOUTS):
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setObjectName("LayoutChoice")
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setIcon(_load_icon(value, icon_name))
            btn.setIconSize(QSize(64, 108))
            btn.setText(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumSize(110, 190)
            btn.clicked.connect(lambda checked=False, v=value: self._on_click(v))
            self._group.addButton(btn)
            self._buttons[value] = btn
            grid.addWidget(btn, i // 2, i % 2)

        self.set_layout(LayoutType.BLUR_CENTER.value)

    def _on_click(self, value: str) -> None:
        self.set_layout(value)
        self.layout_changed.emit(value)

    def set_layout(self, value: str) -> None:
        if value not in self._buttons:
            value = LayoutType.BLUR_CENTER.value
        self._value = value
        for key, btn in self._buttons.items():
            active = key == value
            btn.setChecked(active)
            btn.setProperty("selected", "true" if active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def currentData(self) -> str:
        return self._value

    def findData(self, value: str) -> int:
        keys = list(self._buttons.keys())
        try:
            return keys.index(value)
        except ValueError:
            return -1

    def setCurrentIndex(self, index: int) -> None:
        keys = list(self._buttons.keys())
        if 0 <= index < len(keys):
            self.set_layout(keys[index])
