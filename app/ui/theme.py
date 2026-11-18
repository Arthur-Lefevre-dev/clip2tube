"""Friendly, high-readability Qt theme (large text, clear actions)."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

COLORS = {
    "bg": "#12141a",
    "surface": "#1a1e28",
    "surface_alt": "#242a38",
    "border": "#343b4d",
    "text": "#f2f4f8",
    "text_muted": "#a7b0c0",
    "accent": "#7c4dff",
    "accent_hover": "#9a74ff",
    "success": "#2fbf71",
    "warning": "#f0a202",
    "danger": "#e5484d",
    "nav_active": "#2a2140",
}

STYLESHEET = f"""
QWidget {{
    background-color: {COLORS["bg"]};
    color: {COLORS["text"]};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 15px;
}}

QMainWindow, QDialog {{
    background-color: {COLORS["bg"]};
}}

QMenuBar {{
    background-color: {COLORS["surface"]};
    padding: 4px;
    font-size: 14px;
}}

QMenuBar::item:selected {{
    background: {COLORS["surface_alt"]};
}}

/* Sidebar */
#Sidebar {{
    background-color: {COLORS["surface"]};
    border-right: 1px solid {COLORS["border"]};
}}

#BrandLabel {{
    font-size: 22px;
    font-weight: 800;
    color: {COLORS["text"]};
    padding: 8px 10px 0 10px;
}}

#BrandSub {{
    font-size: 13px;
    color: {COLORS["text_muted"]};
    padding: 2px 10px 16px 10px;
}}

QPushButton#NavButton {{
    background-color: transparent;
    border: none;
    border-radius: 12px;
    text-align: left;
    padding: 14px 16px;
    color: {COLORS["text_muted"]};
    font-size: 15px;
    font-weight: 600;
    min-height: 22px;
}}

QPushButton#NavButton:hover {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
}}

QPushButton#NavButton[active="true"] {{
    background-color: {COLORS["nav_active"]};
    color: {COLORS["accent_hover"]};
}}

QPushButton#NavButton[step="true"] {{
    font-size: 15px;
}}

/* Headers */
#PageTitle {{
    font-size: 28px;
    font-weight: 800;
    color: {COLORS["text"]};
}}

#PageSubtitle {{
    font-size: 15px;
    color: {COLORS["text_muted"]};
    line-height: 1.4;
}}

#StepBadge {{
    background-color: {COLORS["accent"]};
    color: white;
    border-radius: 16px;
    padding: 6px 14px;
    font-weight: 700;
    font-size: 14px;
}}

#HelpCard {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 16px;
    padding: 18px;
}}

#HomeCard {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 18px;
}}

#HomeCardTitle {{
    font-size: 20px;
    font-weight: 760;
}}

#HomeCardBody {{
    font-size: 14px;
    color: {COLORS["text_muted"]};
}}

#StatusOk {{
    color: {COLORS["success"]};
    font-weight: 700;
}}

#StatusKo {{
    color: {COLORS["warning"]};
    font-weight: 700;
}}

#PlaceholderCard {{
    background-color: {COLORS["surface"]};
    border: 1px dashed {COLORS["border"]};
    border-radius: 16px;
    padding: 32px;
}}

#PlaceholderTitle {{
    font-size: 18px;
    font-weight: 700;
}}

#PlaceholderBody {{
    font-size: 14px;
    color: {COLORS["text_muted"]};
}}

/* Buttons — large hit targets */
QPushButton {{
    background-color: {COLORS["accent"]};
    color: white;
    border: none;
    border-radius: 12px;
    padding: 12px 22px;
    font-weight: 700;
    font-size: 15px;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: {COLORS["accent_hover"]};
}}

QPushButton:disabled {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["text_muted"]};
}}

QPushButton#SecondaryButton {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
}}

QPushButton#SecondaryButton:hover {{
    background-color: {COLORS["border"]};
}}

QPushButton#BigAction {{
    font-size: 17px;
    padding: 16px 28px;
    border-radius: 14px;
    min-height: 28px;
}}

QPushButton#DangerButton {{
    background-color: {COLORS["danger"]};
}}

/* Inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
    background-color: {COLORS["surface"]};
    border: 2px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 12px 14px;
    font-size: 15px;
    selection-background-color: {COLORS["accent"]};
    min-height: 22px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
    border: 2px solid {COLORS["accent"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 32px;
}}

QListWidget, QTreeWidget, QTableWidget {{
    background-color: {COLORS["surface"]};
    border: 2px solid {COLORS["border"]};
    border-radius: 14px;
    outline: none;
    font-size: 14px;
    padding: 6px;
}}

QListWidget::item {{
    padding: 10px 8px;
    border-radius: 8px;
    margin: 2px;
}}

QListWidget::item:selected {{
    background-color: {COLORS["nav_active"]};
}}

QScrollBar:vertical {{
    background: {COLORS["bg"]};
    width: 12px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {COLORS["border"]};
    border-radius: 6px;
    min-height: 28px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QStatusBar {{
    background-color: {COLORS["surface"]};
    border-top: 1px solid {COLORS["border"]};
    color: {COLORS["text_muted"]};
    font-size: 13px;
    padding: 4px;
}}

QProgressBar {{
    background-color: {COLORS["surface_alt"]};
    border: none;
    border-radius: 10px;
    text-align: center;
    color: {COLORS["text"]};
    height: 22px;
    font-weight: 700;
}}

QProgressBar::chunk {{
    background-color: {COLORS["accent"]};
    border-radius: 10px;
}}

QCheckBox {{
    spacing: 10px;
    font-size: 15px;
}}

QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 2px solid {COLORS["border"]};
    background: {COLORS["surface"]};
}}

QCheckBox::indicator:checked {{
    background: {COLORS["accent"]};
    border-color: {COLORS["accent"]};
}}

QGroupBox {{
    border: 2px solid {COLORS["border"]};
    border-radius: 14px;
    margin-top: 20px;
    padding: 12px 8px 8px 8px;
    font-weight: 700;
    font-size: 15px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 2px;
    padding: 0 8px;
    color: {COLORS["text_muted"]};
    background-color: {COLORS["bg"]};
}}

QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

QLabel#LogLabel, QPlainTextEdit {{
    font-family: Consolas, "Courier New", monospace;
    font-size: 13px;
}}

QHeaderView::section {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
    padding: 10px;
    border: none;
    font-weight: 700;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Apply readable palette + stylesheet."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["surface_alt"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["surface_alt"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS["text"]))
    app.setPalette(palette)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
