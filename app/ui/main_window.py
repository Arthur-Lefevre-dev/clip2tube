"""Main window — simple guided navigation for non-technical users."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
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
from app.ui.dialogs.update_dialog import show_update_result
from app.ui.theme import style_combo, style_menu
from app.ui.workers import UpdateCheckWorker
from app.utils.config import AppConfig
from app.utils.paths import get_asset_path


# Sidebar groups: (section_title, [(id, label, is_main_step), ...])
# Empty section_title = no header (home sits alone under the brand).
NAV_SECTIONS: list[tuple[str, list[tuple[str, str, bool]]]] = [
    (
        "",
        [
            ("home", "Accueil", False),
        ],
    ),
    (
        "Créer une vidéo",
        [
            ("clips", "1  Chercher un clip", True),
            ("process", "2  Monter en vertical", True),
            ("queue", "3  Voir / publier", True),
        ],
    ),
    (
        "Comptes & auto",
        [
            ("accounts", "YouTube & TikTok", False),
            ("autopilot", "Mode automatique", False),
        ],
    ),
    (
        "Réglages",
        [
            ("settings", "Paramètres", False),
            ("logs", "Journal d’activité", False),
        ],
    ),
]


def iter_nav_items() -> list[tuple[str, str, bool]]:
    """Flat list of all nav entries (for menus / lookups)."""
    items: list[tuple[str, str, bool]] = []
    for _section, entries in NAV_SECTIONS:
        items.extend(entries)
    return items


# Back-compat alias used by the View menu
NAV_ITEMS = iter_nav_items()


def load_app_icon() -> QIcon:
    """Load the branded app icon (PNG/ICO), with a painted fallback."""
    icon = QIcon()
    for name in ("icon.ico", "icon.png"):
        path = get_asset_path(name)
        if path.is_file():
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon

    # Fallback if assets are missing
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#1a1e28"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setBrush(QColor("#e84d8a"))
    painter.drawRoundedRect(22, 12, 20, 40, 6, 6)
    painter.setBrush(QColor("white"))
    painter.drawEllipse(28, 26, 8, 8)
    painter.end()
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, database: Database) -> None:
        super().__init__()
        self.config = config
        self.database = database
        self._nav_buttons: dict[str, QPushButton] = {}
        self._page_indexes: dict[str, int] = {}
        self._update_worker: UpdateCheckWorker | None = None
        self._update_silent = False

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
        self._app_icon = load_app_icon()
        self.setWindowIcon(self._app_icon)

        self._build_ui()
        self._bind_pages()
        self._build_menu()
        self._build_tray()
        self._wire_signals()
        self._style_all_combos()
        self._show_page("home")
        self.statusBar().showMessage(
            "Bienvenue — commencez par l’Accueil, puis suivez les étapes 1, 2 et 3."
        )

    def _style_all_combos(self) -> None:
        for combo in self.findChildren(QComboBox):
            style_combo(combo)
        if bool(self.config.get("updates", "check_on_startup", default=True)):
            QTimer.singleShot(2500, lambda: self.check_for_updates(silent=True))

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
        sidebar.setFixedWidth(268)

        col = QVBoxLayout(sidebar)
        col.setContentsMargins(14, 18, 14, 14)
        col.setSpacing(4)

        # Brand row with app icon
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.setContentsMargins(6, 0, 6, 0)
        icon_lbl = QLabel()
        icon_lbl.setObjectName("BrandIcon")
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        pix = self._app_icon.pixmap(QSize(36, 36))
        if not pix.isNull():
            icon_lbl.setPixmap(pix)
            icon_lbl.setFixedSize(36, 36)
            icon_lbl.setScaledContents(True)
            brand_row.addWidget(icon_lbl)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand = QLabel("Clip2Tube")
        brand.setObjectName("BrandLabel")
        brand_text.addWidget(brand)
        brand_sub = QLabel("Twitch → Shorts")
        brand_sub.setObjectName("BrandSub")
        brand_text.addWidget(brand_sub)
        brand_row.addLayout(brand_text, stretch=1)
        col.addLayout(brand_row)
        col.addSpacing(10)

        for section_title, entries in NAV_SECTIONS:
            if section_title:
                # Distinct card per section (Créer / Comptes / Réglages)
                col.addSpacing(12)
                group = QFrame()
                group.setObjectName("NavGroup")
                group_lay = QVBoxLayout(group)
                group_lay.setContentsMargins(8, 10, 8, 8)
                group_lay.setSpacing(4)

                header = QLabel(section_title.upper())
                header.setObjectName("NavSection")
                group_lay.addWidget(header)

                for nav_id, label, is_step in entries:
                    btn = QPushButton(label)
                    btn.setObjectName("NavButton")
                    btn.setProperty("step", "true" if is_step else "false")
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.setProperty("active", False)
                    btn.clicked.connect(
                        lambda checked=False, i=nav_id: self._show_page(i)
                    )
                    self._nav_buttons[nav_id] = btn
                    group_lay.addWidget(btn)
                col.addWidget(group)
            else:
                for nav_id, label, is_step in entries:
                    btn = QPushButton(label)
                    btn.setObjectName("NavButton")
                    btn.setProperty("step", "true" if is_step else "false")
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.setProperty("active", False)
                    btn.clicked.connect(
                        lambda checked=False, i=nav_id: self._show_page(i)
                    )
                    self._nav_buttons[nav_id] = btn
                    col.addWidget(btn)

        col.addStretch(1)

        foot = QLabel(f"v{__version__}")
        foot.setObjectName("NavFooter")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(foot)
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
        self.clips_page.bind(self.twitch, self.database, self.config)
        self.process_page.bind(self.pipeline, self.config)
        self.queue_page.bind(self.database, self.pipeline)
        self.accounts_page.bind(self.youtube, self.tiktok)
        self.autopilot_page.bind(self.scheduler, self.config, self.database)
        self.settings_page.bind(self.config)
        self.logs_page.bind(self.database)

    def _wire_signals(self) -> None:
        self.home_page.go_to.connect(self._show_page)
        self.home_page.streamers_changed.connect(self._on_streamers_changed)
        self.clips_page.clips_selected.connect(self._on_clips_selected)
        self.clips_page.log_requested.connect(self._log)
        self.clips_page.go_settings.connect(lambda: self._show_page("settings"))
        self.clips_page.go_home.connect(lambda: self._show_page("home"))
        self.process_page.log_requested.connect(self._log)
        self.process_page.job_done.connect(self._on_job_done)
        self.process_page.go_to.connect(self._show_page)
        self.queue_page.log_requested.connect(self._log)
        self.accounts_page.log_requested.connect(self._log)
        self.autopilot_page.log_requested.connect(self._log)
        self.settings_page.log_requested.connect(self._log)
        self.settings_page.saved.connect(self._on_settings_saved)
        self.settings_page.check_updates_requested.connect(
            lambda: self.check_for_updates(silent=False)
        )
        self.scheduler.log_message.connect(self._log)
        self.scheduler.job_updated.connect(lambda _j: self.queue_page.refresh())

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&Fichier")
        style_menu(file_menu)
        quit_action = QAction("Quitter complètement", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self._quit_app)
        file_menu.addAction(quit_action)

        view_menu = menu.addMenu("&Aller à")
        style_menu(view_menu)
        for nav_id, label, _ in NAV_ITEMS:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, i=nav_id: self._show_page(i))
            view_menu.addAction(action)

        help_menu = menu.addMenu("&Aide")
        style_menu(help_menu)
        about = QAction("Comment ça marche ?", self)
        about.triggered.connect(lambda: self._show_page("home"))
        help_menu.addAction(about)
        update_action = QAction("Vérifier les mises à jour…", self)
        update_action.triggered.connect(lambda: self.check_for_updates(silent=False))
        help_menu.addAction(update_action)

    def check_for_updates(self, *, silent: bool = False) -> None:
        """Start a background GitHub Releases check."""
        if self._update_worker and self._update_worker.isRunning():
            if not silent:
                self.statusBar().showMessage("Vérification déjà en cours…")
            return
        self._update_silent = silent
        repo = str(
            self.config.get(
                "updates",
                "github_repo",
                default="Arthur-Lefevre-dev/clip2tube",
            )
            or "Arthur-Lefevre-dev/clip2tube"
        )
        if not silent:
            self.statusBar().showMessage("Recherche de mise à jour…")
            self._log("Vérification des mises à jour en ligne…")
        self._update_worker = UpdateCheckWorker(__version__, repo, parent=self)
        self._update_worker.finished_ok.connect(self._on_update_checked)
        self._update_worker.failed.connect(self._on_update_failed)
        self._update_worker.start()

    def _on_update_checked(self, info) -> None:
        show_update_result(self, info, silent_if_up_to_date=self._update_silent)
        if info.available:
            self._log(
                f"Mise à jour disponible : {info.latest_version} "
                f"(actuelle {info.current_version})"
            )
            self.statusBar().showMessage(
                f"Nouvelle version {info.latest_version} disponible"
            )
        elif not info.error and not self._update_silent:
            self.statusBar().showMessage(
                f"Clip2Tube est à jour ({info.current_version})"
            )

    def _on_update_failed(self, message: str) -> None:
        self._log(f"Mise à jour : {message}")
        if self._update_silent:
            return
        QMessageBox.warning(self, "Mise à jour", message)

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._app_icon)
        self.tray.setToolTip("Clip2Tube")
        tray_menu = QMenu()
        style_menu(tray_menu)
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

    def _on_streamers_changed(self) -> None:
        # Keep Settings bulk list in sync when Accueil CRUD saves
        self.settings_page.refresh_from_config()
        self.clips_page.refresh()
        n = len(self.config.get("followed_streamers", default=[]) or [])
        self.statusBar().showMessage(f"Streamers suivis : {n}")

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
        if nav_id == "clips":
            self.clips_page.refresh()
        if nav_id == "settings":
            self.settings_page.refresh_from_config()
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
