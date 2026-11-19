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
/* Do NOT paint an opaque background on every QWidget — that creates
   black rectangles behind labels inside cards/hero. */
QWidget {{
    color: {COLORS["text"]};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 15px;
    background-color: transparent;
}}

QMainWindow, QDialog, QStackedWidget {{
    background-color: {COLORS["bg"]};
}}

QLabel {{
    background-color: transparent;
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
    font-size: 18px;
    font-weight: 800;
    color: {COLORS["text"]};
    padding: 0;
    background-color: transparent;
}}

#BrandSub {{
    font-size: 12px;
    color: {COLORS["text_muted"]};
    padding: 0;
    background-color: transparent;
}}

#BrandIcon {{
    background-color: transparent;
    border: none;
}}

#NavGroup {{
    background-color: {COLORS["bg"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 14px;
}}

#NavSection {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.8px;
    color: {COLORS["text_muted"]};
    padding: 4px 6px 6px 6px;
    background-color: transparent;
}}

#NavFooter {{
    font-size: 12px;
    color: {COLORS["text_muted"]};
    padding: 10px 8px 4px 8px;
    background-color: transparent;
}}

QPushButton#NavButton {{
    background-color: transparent;
    border: none;
    border-radius: 10px;
    text-align: left;
    padding: 11px 14px;
    color: {COLORS["text_muted"]};
    font-size: 14px;
    font-weight: 600;
    min-height: 18px;
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
    font-size: 14px;
    font-weight: 700;
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

#HelpCard {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 16px;
    padding: 18px;
}}

#HomeHero {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 20px;
}}

#HomeEyebrow {{
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: {COLORS["accent_hover"]};
}}

#HomeSectionTitle {{
    font-size: 18px;
    font-weight: 760;
    color: {COLORS["text"]};
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

QLabel#EmptyHint {{
    font-size: 14px;
    color: {COLORS["text_muted"]};
    padding: 28px 12px;
    background-color: {COLORS["surface_alt"]};
    border: 1px dashed {COLORS["border"]};
    border-radius: 12px;
}}

QLabel#StreamerCount {{
    font-size: 13px;
    font-weight: 700;
    color: {COLORS["accent_hover"]};
    background-color: {COLORS["nav_active"]};
    border-radius: 10px;
    padding: 4px 10px;
}}

QLabel#StepBadge {{
    background-color: {COLORS["accent"]};
    color: white;
    border-radius: 16px;
    padding: 6px 14px;
    font-weight: 700;
    font-size: 14px;
}}

#ProcessCard {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 16px;
}}

#ProcessCardTitle {{
    font-size: 15px;
    font-weight: 760;
    color: {COLORS["text"]};
    background-color: transparent;
}}

#ProcessHint {{
    font-size: 13px;
    color: {COLORS["text_muted"]};
    background-color: transparent;
}}

#PreviewShell {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 20px;
}}

#PreviewPhone {{
    background-color: #000000;
    border: 2px solid {COLORS["border"]};
    border-radius: 18px;
}}

#PreviewPhone QVideoWidget {{
    background-color: #000000;
    border-radius: 16px;
}}

#PreviewEmpty {{
    font-size: 14px;
    color: {COLORS["text_muted"]};
    background-color: transparent;
}}

#ClipCountBadge {{
    font-size: 12px;
    font-weight: 700;
    color: {COLORS["accent_hover"]};
    background-color: {COLORS["nav_active"]};
    border-radius: 10px;
    padding: 4px 10px;
}}

QToolButton#LayoutChoice {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
    border: 2px solid {COLORS["border"]};
    border-radius: 14px;
    padding: 8px 6px 10px 6px;
    font-size: 11px;
    font-weight: 700;
    min-width: 112px;
    max-width: 112px;
    min-height: 112px;
    max-height: 112px;
}}

QToolButton#LayoutChoice:hover {{
    border-color: {COLORS["accent_hover"]};
    background-color: {COLORS["surface"]};
}}

QToolButton#LayoutChoice:checked,
QToolButton#LayoutChoice[selected="true"] {{
    border: 2px solid {COLORS["accent"]};
    background-color: {COLORS["nav_active"]};
    color: {COLORS["accent_hover"]};
}}

#StatusOk {{
    color: {COLORS["success"]};
    font-weight: 700;
}}

#StatusKo {{
    color: {COLORS["warning"]};
    font-weight: 700;
}}

#SetupTile {{
    background-color: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 14px;
}}

#SetupTile[state="ok"] {{
    border: 1px solid {COLORS["success"]};
    background-color: #1a2a22;
}}

#SetupTile[state="todo"] {{
    border: 1px solid {COLORS["warning"]};
    background-color: #2a2418;
}}

#SetupTile[state="optional"] {{
    border: 1px solid {COLORS["border"]};
}}

#SetupStep {{
    font-size: 12px;
    font-weight: 800;
    color: {COLORS["text_muted"]};
    min-width: 16px;
}}

#SetupTitle {{
    font-size: 15px;
    font-weight: 760;
    color: {COLORS["text"]};
}}

#SetupSubtitle {{
    font-size: 12px;
    color: {COLORS["text_muted"]};
}}

#SetupDetail {{
    font-size: 13px;
    color: {COLORS["text"]};
    padding-top: 2px;
}}

#SetupBadge {{
    font-size: 12px;
    font-weight: 800;
    padding: 3px 8px;
    border-radius: 8px;
    background-color: {COLORS["border"]};
    color: {COLORS["text"]};
}}

#SetupBadge[state="ok"] {{
    background-color: {COLORS["success"]};
    color: #0b1410;
}}

#SetupBadge[state="todo"] {{
    background-color: {COLORS["warning"]};
    color: #1a1200;
}}

#SetupBadge[state="optional"] {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_muted"]};
}}

QListWidget#StreamerList {{
    background-color: {COLORS["bg"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 14px;
    padding: 10px;
}}

QListWidget#StreamerList::item {{
    background-color: transparent;
    border: none;
    margin: 0 0 12px 0;
    padding: 0;
}}

QListWidget#StreamerList::item:selected {{
    background-color: transparent;
}}

#StreamerRow {{
    background-color: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
}}

#StreamerRow:hover {{
    border-color: {COLORS["accent_hover"]};
}}

#StreamerRow[selected="true"] {{
    border: 2px solid {COLORS["accent"]};
    background-color: {COLORS["nav_active"]};
}}

#StreamerAvatar {{
    background-color: {COLORS["nav_active"]};
    border-radius: 24px;
    color: {COLORS["accent_hover"]};
    font-weight: 800;
    font-size: 16px;
}}

#StreamerDisplayName {{
    font-size: 15px;
    font-weight: 760;
    color: {COLORS["text"]};
}}

#StreamerLogin {{
    font-size: 12px;
    color: {COLORS["text_muted"]};
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
QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
    background-color: {COLORS["surface"]};
    border: 2px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 12px 14px;
    font-size: 15px;
    selection-background-color: {COLORS["accent"]};
    min-height: 22px;
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
    border: 2px solid {COLORS["accent"]};
}}

/* MenuCombo = button + QMenu (reliable rounded popup, no Fusion bleed) */
QPushButton#MenuCombo {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text"]};
    border: 2px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 12px 42px 12px 20px;
    text-align: left;
    font-size: 15px;
    font-weight: 600;
    min-height: 22px;
}}

QPushButton#MenuCombo:hover {{
    background-color: {COLORS["surface_alt"]};
    border-color: {COLORS["accent"]};
}}

QPushButton#MenuCombo::menu-indicator {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 16px;
    height: 16px;
    right: 12px;
    image: url(__CHEVRON_DOWN__);
}}

/* Menus (File / Aide / tray / MenuCombo) — inset items, no corner bleed */
QMenu {{
    background-color: {COLORS["surface"]};
    border: 2px solid {COLORS["border"]};
    border-radius: 14px;
    padding: 8px;
}}

QMenu::item {{
    margin: 3px 4px;
    padding: 10px 18px;
    border-radius: 8px;
    color: {COLORS["text"]};
    background-color: transparent;
}}

QMenu::item:selected {{
    background-color: {COLORS["nav_active"]};
    color: {COLORS["accent_hover"]};
}}

QMenu::separator {{
    height: 1px;
    background: {COLORS["border"]};
    margin: 8px 12px;
}}

/* Classic spin box: value left, +/− stacked on the right */
QSpinBox, QDoubleSpinBox {{
    color: {COLORS["text"]};
    padding-right: 38px;
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 34px;
    background-color: {COLORS["surface_alt"]};
    border: none;
    border-left: 2px solid {COLORS["border"]};
    border-top-right-radius: 10px;
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 34px;
    background-color: {COLORS["surface_alt"]};
    border: none;
    border-left: 2px solid {COLORS["border"]};
    border-bottom-right-radius: 10px;
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {COLORS["accent"]};
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url(__SPIN_PLUS__);
    width: 14px;
    height: 14px;
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url(__SPIN_MINUS__);
    width: 14px;
    height: 14px;
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

/* Clip search results */
QListWidget#ClipList {{
    background-color: {COLORS["bg"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 16px;
    padding: 12px;
}}

QListWidget#ClipList::item {{
    background-color: transparent;
    border: none;
    border-radius: 0;
    margin: 0 0 14px 0;
    padding: 0;
}}

QListWidget#ClipList::item:selected {{
    background-color: transparent;
}}

QListWidget#ClipList::item:hover {{
    background-color: transparent;
}}

#ClipRow {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 14px;
}}

#ClipRow:hover {{
    border-color: {COLORS["accent"]};
    background-color: {COLORS["surface_alt"]};
}}

#ClipThumb {{
    background-color: {COLORS["surface_alt"]};
    border-radius: 10px;
    color: {COLORS["text_muted"]};
}}

#ClipDuration {{
    background-color: rgba(0, 0, 0, 180);
    color: {COLORS["text"]};
    font-size: 12px;
    font-weight: 700;
    padding: 3px 7px;
    border-radius: 6px;
}}

#ClipTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {COLORS["text"]};
    padding: 0;
}}

#ClipStreamer {{
    font-size: 13px;
    font-weight: 700;
    color: {COLORS["accent_hover"]};
}}

#ClipMeta {{
    font-size: 13px;
    color: {COLORS["text_muted"]};
}}

#ClipSep {{
    font-size: 13px;
    color: {COLORS["border"]};
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
    image: url(__CHECK_X__);
}}

QCheckBox::indicator:checked:hover {{
    background: {COLORS["accent_hover"]};
    border-color: {COLORS["accent_hover"]};
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
    background-color: transparent;
    border: none;
}}

QScrollArea > QWidget {{
    background-color: transparent;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QAbstractScrollArea::viewport {{
    background-color: transparent;
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


def style_spinbox(spin) -> None:
    """Classic up/down buttons; icons come from the stylesheet PNGs."""
    from PySide6.QtWidgets import QAbstractSpinBox

    # UpDownArrows + PNG +/− (PlusMinus text is often invisible with QSS)
    spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)


def style_combo(combo) -> None:
    """Legacy no-op — prefer MenuCombo (QMenu) for dropdowns."""
    return


def style_menu(menu) -> None:
    """Rounded menu without corner bleed on selected items."""
    from PySide6.QtCore import Qt

    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    menu.setWindowFlags(
        menu.windowFlags()
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.NoDropShadowWindowHint
    )


def _qss_url(path) -> str:
    """Quoted absolute path for Qt stylesheet url(...)."""
    return '"' + path.resolve().as_posix() + '"'


def _stylesheet_with_assets() -> str:
    """Resolve icon paths inside the QSS."""
    from app.utils.paths import get_asset_path

    css = STYLESHEET
    replacements = {
        "__CHEVRON_DOWN__": get_asset_path("chevron_down.png"),
        "__SPIN_PLUS__": get_asset_path("spin_plus.png"),
        "__SPIN_MINUS__": get_asset_path("spin_minus.png"),
        "__CHECK_X__": get_asset_path("check_x.png"),
    }
    for token, path in replacements.items():
        if path.is_file():
            css = css.replace(token, _qss_url(path))
        else:
            css = css.replace(f"image: url({token});", "/* asset missing */")
    return css


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
    app.setStyleSheet(_stylesheet_with_assets())
