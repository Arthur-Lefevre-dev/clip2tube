"""Illustrated layout style picker — equal square tiles in a row."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QSizePolicy, QToolButton, QWidget

from app.models import LayoutType
from app.utils.paths import get_asset_path

# Equal square tiles side by side (5 options)
TILE = 112
ICON_W = 42
ICON_H = 70

_LAYOUTS: list[tuple[str, str, str]] = [
    (
        LayoutType.BLUR_CENTER.value,
        "Fond flou\n★ reco",
        "blur_center.png",
    ),
    (
        LayoutType.FILL_HEIGHT.value,
        "Plein écran\nsans cam",
        "fill_height.png",
    ),
    (
        LayoutType.FACECAM_SPLIT.value,
        "Webcam\nhaut gauche",
        "facecam_split.png",
    ),
    (
        LayoutType.FACECAM_QUARTER.value,
        "1/4 cam\n3/4 vidéo",
        "facecam_quarter.png",
    ),
    (
        LayoutType.LETTERBOX.value,
        "Barres\nletterbox",
        "letterbox.png",
    ),
]


def _fallback_icon(kind: str) -> QPixmap:
    pix = QPixmap(ICON_W, ICON_H)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#1a1e28"))
    p.setPen(QPen(QColor("#343b4d"), 2))
    p.drawRoundedRect(2, 2, ICON_W - 4, ICON_H - 4, 10, 10)
    if kind == LayoutType.BLUR_CENTER.value:
        p.setBrush(QColor("#3c3250"))
        p.drawRoundedRect(6, 6, ICON_W - 12, ICON_H - 12, 8, 8)
        p.setBrush(QColor("#7864a0"))
        p.drawRoundedRect(12, 22, ICON_W - 24, 28, 6, 6)
    elif kind == LayoutType.FILL_HEIGHT.value:
        # Full cover — gameplay fills the whole phone
        p.setBrush(QColor("#2a6a8a"))
        p.drawRoundedRect(6, 6, ICON_W - 12, ICON_H - 12, 8, 8)
        p.setBrush(QColor("#5eb0d0"))
        p.drawRoundedRect(14, 18, ICON_W - 28, ICON_H - 36, 4, 4)
    elif kind == LayoutType.FACECAM_SPLIT.value:
        p.setBrush(QColor("#28465a"))
        p.drawRoundedRect(6, 6, ICON_W - 12, ICON_H - 12, 8, 8)
        p.setBrush(QColor("#e84d8a"))
        p.drawRoundedRect(8, 8, 18, 22, 5, 5)
    elif kind == LayoutType.FACECAM_QUARTER.value:
        p.setBrush(QColor("#e84d8a"))
        p.drawRoundedRect(6, 6, ICON_W - 12, 16, 4, 4)
        p.setBrush(QColor("#28465a"))
        p.drawRoundedRect(6, 26, ICON_W - 12, ICON_H - 34, 4, 4)
    else:
        p.setBrush(QColor("#0a0c10"))
        p.drawRect(6, 6, ICON_W - 12, 10)
        p.drawRect(6, ICON_H - 16, ICON_W - 12, 10)
        p.setBrush(QColor("#5a6e8c"))
        p.drawRoundedRect(8, 20, ICON_W - 16, 32, 3, 3)
    p.end()
    return pix


def _load_icon(value: str, icon_name: str) -> QIcon:
    path = get_asset_path("layouts", icon_name)
    if path.is_file():
        pix = QPixmap(str(path)).scaled(
            ICON_W,
            ICON_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    else:
        pix = _fallback_icon(value)
    return QIcon(pix)


class LayoutPicker(QWidget):
    """Equal square toggle tiles for vertical layout styles."""

    layout_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._value = LayoutType.BLUR_CENTER.value
        self._buttons: dict[str, QToolButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._build()

    def _build(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        for value, label, icon_name in _LAYOUTS:
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setObjectName("LayoutChoice")
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setIcon(_load_icon(value, icon_name))
            btn.setIconSize(QSize(ICON_W, ICON_H))
            btn.setText(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(TILE, TILE)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda checked=False, v=value: self._on_click(v))
            self._group.addButton(btn)
            self._buttons[value] = btn
            row.addWidget(btn)

        row.addStretch(1)
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
