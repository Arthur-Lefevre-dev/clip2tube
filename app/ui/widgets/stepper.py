"""Spin controls with explicit − / + buttons (readable on dark themes)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QWidget,
)


class StepperSpinBox(QWidget):
    """Integer spin box with large − / + buttons instead of tiny empty arrows."""

    valueChanged = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.spin = QSpinBox()
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.valueChanged.connect(self.valueChanged.emit)
        self._build(self.spin)

    def _build(self, spin: QAbstractSpinBox) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.minus_btn = QPushButton("−")
        self.minus_btn.setObjectName("StepperButton")
        self.minus_btn.setFixedSize(40, 40)
        self.minus_btn.clicked.connect(spin.stepDown)

        self.plus_btn = QPushButton("+")
        self.plus_btn.setObjectName("StepperButton")
        self.plus_btn.setFixedSize(40, 40)
        self.plus_btn.clicked.connect(spin.stepUp)

        row.addWidget(self.minus_btn)
        row.addWidget(spin, stretch=1)
        row.addWidget(self.plus_btn)

    def setRange(self, minimum: int, maximum: int) -> None:
        self.spin.setRange(minimum, maximum)

    def setValue(self, value: int) -> None:
        self.spin.setValue(value)

    def value(self) -> int:
        return self.spin.value()

    def setSingleStep(self, step: int) -> None:
        self.spin.setSingleStep(step)

    def setMinimumWidth(self, width: int) -> None:
        self.spin.setMinimumWidth(max(60, width - 90))
        super().setMinimumWidth(width)

    def setToolTip(self, tip: str) -> None:
        self.spin.setToolTip(tip)
        super().setToolTip(tip)

    def setSuffix(self, suffix: str) -> None:
        self.spin.setSuffix(suffix)


class StepperDoubleSpinBox(QWidget):
    """Decimal spin box with large − / + buttons."""

    valueChanged = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.spin = QDoubleSpinBox()
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.valueChanged.connect(self.valueChanged.emit)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.minus_btn = QPushButton("−")
        self.minus_btn.setObjectName("StepperButton")
        self.minus_btn.setFixedSize(40, 40)
        self.minus_btn.clicked.connect(self.spin.stepDown)

        self.plus_btn = QPushButton("+")
        self.plus_btn.setObjectName("StepperButton")
        self.plus_btn.setFixedSize(40, 40)
        self.plus_btn.clicked.connect(self.spin.stepUp)

        row.addWidget(self.minus_btn)
        row.addWidget(self.spin, stretch=1)
        row.addWidget(self.plus_btn)

    def setRange(self, minimum: float, maximum: float) -> None:
        self.spin.setRange(minimum, maximum)

    def setValue(self, value: float) -> None:
        self.spin.setValue(value)

    def value(self) -> float:
        return self.spin.value()

    def setSingleStep(self, step: float) -> None:
        self.spin.setSingleStep(step)

    def setMaximumWidth(self, width: int) -> None:
        super().setMaximumWidth(width)
