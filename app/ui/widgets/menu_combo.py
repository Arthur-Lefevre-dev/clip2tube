"""Dropdown built with QMenu — same rounded look as the tray menu (no QComboBox chrome)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QPushButton, QMenu

from app.ui.theme import style_menu


class MenuCombo(QPushButton):
    """
    Select control that pops a QMenu instead of QComboBox.

    Avoids Windows Fusion artifacts (square popup, background past border-radius).
    """

    currentIndexChanged = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MenuCombo")
        from PySide6.QtCore import Qt

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._items: list[tuple[str, Any]] = []
        self._index = -1
        self._menu = QMenu(self)
        style_menu(self._menu)
        self.setMenu(self._menu)
        self.setMinimumHeight(48)

    def _display_text(self, text: str) -> str:
        # Leading spaces: Qt often ignores left padding on QPushButton + menu
        return f"  {text}" if text else text

    def addItem(self, text: str, userData: Any = None) -> None:
        idx = len(self._items)
        self._items.append((text, userData))
        action = QAction(text, self._menu)
        action.triggered.connect(lambda checked=False, i=idx: self._select(i))
        self._menu.addAction(action)
        if self._index < 0:
            self.setCurrentIndex(0)

    def clear(self) -> None:
        self._menu.clear()
        self._items.clear()
        self._index = -1
        self.setText("")

    def count(self) -> int:
        return len(self._items)

    def currentIndex(self) -> int:
        return self._index

    def currentText(self) -> str:
        if 0 <= self._index < len(self._items):
            return self._items[self._index][0]
        return ""

    def currentData(self) -> Any:
        if 0 <= self._index < len(self._items):
            return self._items[self._index][1]
        return None

    def itemData(self, index: int) -> Any:
        if 0 <= index < len(self._items):
            return self._items[index][1]
        return None

    def itemText(self, index: int) -> str:
        if 0 <= index < len(self._items):
            return self._items[index][0]
        return ""

    def findData(self, data: Any) -> int:
        for i, (_t, d) in enumerate(self._items):
            if d == data:
                return i
        return -1

    def findText(self, text: str) -> int:
        for i, (t, _d) in enumerate(self._items):
            if t == text:
                return i
        return -1

    def setCurrentIndex(self, index: int) -> None:
        if index < 0 or index >= len(self._items):
            return
        label = self._display_text(self._items[index][0])
        if index == self._index:
            self.setText(label)
            return
        self._index = index
        self.setText(label)
        self.currentIndexChanged.emit(index)

    def setCurrentText(self, text: str) -> None:
        idx = self.findText(text)
        if idx >= 0:
            self.setCurrentIndex(idx)

    def _select(self, index: int) -> None:
        self.setCurrentIndex(index)
