"""Main window — simple guided navigation for non-technical users."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
    QApplication,
)

from app import __version__
from app.db import Database
from app.services.pipeline import PipelineService
from app.services.scheduler import SchedulerService
from app.services.tiktok import TikTokService
from app.services.twitch import TwitchService
from app.services.youtube import YouTubeService
from app.ui.pages import (
    AccountsPage,
    AutopilotPage,
    ClipsPage,
    HomePage,
    LogsPage,
    ProcessPage,
    QueuePage,
    SettingsPage,
)
from app.utils.config import AppConfig


# Main journey first, then less-used screens
NAV_ITEMS: list[tuple[str, str, bool]] = [
    # id, label, is_main_step
    ("home", "Accueil", False),
    ("clips", "1 · Chercher des clips", True),
    ("process", "2 · Créer ma vidéo", True),
    ("queue", "3 · Mes vidéos", True),
    ("accounts", "Comptes YouTube / TikTok", False),
    ("settings", "Réglages", False),
    ("autopilot", "Mode automatique", False),
    ("logs", "Journal", False),
]


def _make_tray_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#7c4dff"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setPen(QColor("white"))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "C2")
    painter.end()
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, database: Database) -> None:
        super().__init__()
        self.config = config
        self.database = database
        self._nav_buttons: dict[str, QPushButton] = {}
        self._page_indexes: dict[str, int] = {}

        self.twitch = TwitchService(config)
        self.youtube = YouTubeService(config, database)
        self.tiktok = TikTokService(config, database)
        self.pipeline = PipelineService(config, database, self.youtube, self.tiktok)
        self.scheduler = SchedulerService(
            config, database, self.pipeline, self.twitch, parent=self
        )

        self.setWindowTitle(f"Clip2Tube — clips Twitch en vidéos verticales")
        self.setMinimumSize(QSize(1180, 740))
        self.resize(1360, 860)
        self.setWindowIcon(_make_tray_icon())

        self._build_ui()
        self._bind_pages()
        self._build_menu()
        self._build_tray()
        self._wire_signals()
        self._show_page("home")
        self.statusBar().showMessage(
            "Bienvenue — commencez par l’Accueil, puis suivez les étapes 1, 2 et 3."
        )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_stack(), stretch=1)
        self.setStatusBar(QStatusBar())

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)

        col = QVBoxLayout(sidebar)
        col.setContentsMargins(14, 22, 14, 16)
        col.setSpacing(6)

        brand = QLabel("Clip2Tube")
        brand.setObjectName("BrandLabel")
        col.addWidget(brand)

        brand_sub = QLabel("Des clips Twitch → des Shorts")
        brand_sub.setObjectName("BrandSub")
        col.addWidget(brand_sub)

        for nav_id, label, is_step in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setProperty("step", is_step)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("active", False)
            btn.clicked.connect(lambda checked=False, i=nav_id: self._show_page(i))
            self._nav_buttons[nav_id] = btn
            col.addWidget(btn)
            if nav_id == "queue":
                # Visual separator after the main 3 steps
                sep = QLabel("Plus d’options")
                sep.setObjectName("BrandSub")
                col.addWidget(sep)

        col.addStretch(1)
        version = QLabel(f"Version {__version__}")
        version.setObjectName("BrandSub")
        col.addWidget(version)
        return sidebar

    def _build_stack(self) -> QStackedWidget:
        self.stack = QStackedWidget()
        self.home_page = HomePage()
        self.clips_page = ClipsPage()
        self.process_page = ProcessPage()
        self.queue_page = QueuePage()
        self.accounts_page = AccountsPage()
        self.autopilot_page = AutopilotPage()
        self.settings_page = SettingsPage()
        self.logs_page = LogsPage()

        pages = [
            ("home", self.home_page),
            ("clips", self.clips_page),
            ("process", self.process_page),
            ("queue", self.queue_page),
            ("accounts", self.accounts_page),
            ("autopilot", self.autopilot_page),
            ("settings", self.settings_page),
            ("logs", self.logs_page),
        ]
        for nav_id, page in pages:
            self._page_indexes[nav_id] = self.stack.addWidget(page)
        return self.stack

    def _bind_pages(self) -> None:
        self.home_page.bind(self.config, self.twitch, self.youtube)
        self.clips_page.bind(self.twitch, self.database)
        self.process_page.bind(self.pipeline, self.config)
        self.queue_page.bind(self.database, self.pipeline)
        self.accounts_page.bind(self.youtube, self.tiktok)
        self.autopilot_page.bind(self.scheduler, self.config, self.database)
        self.settings_page.bind(self.config)
        self.logs_page.bind(self.database)

    def _wire_signals(self) -> None:
        self.home_page.go_to.connect(self._show_page)
        self.clips_page.clips_selected.connect(self._on_clips_selected)
        self.clips_page.log_requested.connect(self._log)
        self.clips_page.go_settings.connect(lambda: self._show_page("settings"))
        self.process_page.log_requested.connect(self._log)
        self.process_page.job_done.connect(self._on_job_done)
        self.queue_page.log_requested.connect(self._log)
        self.accounts_page.log_requested.connect(self._log)
        self.autopilot_page.log_requested.connect(self._log)
        self.settings_page.log_requested.connect(self._log)
        self.settings_page.saved.connect(self._on_settings_saved)
        self.scheduler.log_message.connect(self._log)
        self.scheduler.job_updated.connect(lambda _j: self.queue_page.refresh())

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&Fichier")
        quit_action = QAction("Quitter complètement", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self._quit_app)
        file_menu.addAction(quit_action)

        view_menu = menu.addMenu("&Aller à")
        for nav_id, label, _ in NAV_ITEMS:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, i=nav_id: self._show_page(i))
            view_menu.addAction(action)

        help_menu = menu.addMenu("&Aide")
        about = QAction("Comment ça marche ?", self)
        about.triggered.connect(lambda: self._show_page("home"))
        help_menu.addAction(about)

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(_make_tray_icon())
        self.tray.setToolTip("Clip2Tube")
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Afficher Clip2Tube")
        show_action.triggered.connect(self._restore_from_tray)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quitter")
        quit_action.triggered.connect(self._quit_app)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_clips_selected(self, clips) -> None:
        self.process_page.set_clips(clips)
        self._show_page("process")
        self._log(f"{len(clips)} clip(s) prêts pour la création")

    def _on_job_done(self, job) -> None:
        self.queue_page.refresh()
        self._log(f"Vidéo prête : {job.clip_title}")

    def _on_settings_saved(self) -> None:
        ffmpeg = str(self.config.get("ffmpeg_path", default="") or "")
        self.pipeline.editor.ffmpeg_path = ffmpeg
        self.pipeline.subtitles.ffmpeg_path = ffmpeg
        self.home_page.refresh()
        self.statusBar().showMessage("Réglages enregistrés — vous pouvez chercher des clips.")

    def _log(self, message: str) -> None:
        self.logs_page.append(message)
        self.statusBar().showMessage(message[:140])

    def _show_page(self, nav_id: str) -> None:
        index = self._page_indexes.get(nav_id)
        if index is None:
            return
        self.stack.setCurrentIndex(index)
        for key, btn in self._nav_buttons.items():
            is_active = key == nav_id
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()
        if nav_id == "queue":
            self.queue_page.refresh()
        if nav_id == "home":
            self.home_page.refresh()
        if nav_id == "accounts":
            self.accounts_page.refresh()
        labels = {i: lbl for i, lbl, _ in NAV_ITEMS}
        self.statusBar().showMessage(f"Vous êtes ici : {labels.get(nav_id, nav_id)}")

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.tray and self.tray.isVisible():
            self.hide()
            self.tray.showMessage(
                "Clip2Tube",
                "L’appli continue en arrière-plan. Clic droit sur l’icône → Quitter.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
            event.ignore()
            return
        event.accept()

    def _quit_app(self) -> None:
        if self.tray:
            self.tray.hide()
        self.scheduler.stop_auto_pilot()
        QApplication.instance().quit()
