"""Clip search page — plain-language UX."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models import Clip
from app.ui.theme import style_spinbox
from app.ui.widgets.clip_row import ClipRowWidget
from app.ui.widgets.menu_combo import MenuCombo
from app.ui.workers import SearchClipsWorker


class ClipsPage(QWidget):
    clips_selected = Signal(list)
    log_requested = Signal(str)
    go_settings = Signal()
    go_home = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._twitch = None
        self._db = None
        self._config = None
        self._worker: Optional[SearchClipsWorker] = None
        self._clips: list[Clip] = []
        self._rows: dict[str, ClipRowWidget] = {}
        self._net = QNetworkAccessManager(self)
        self._build()

    def bind(self, twitch, database, config=None) -> None:
        self._twitch = twitch
        self._db = database
        self._config = config
        self._refresh_followed_label()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(14)

        badge = QLabel("Étape 1")
        badge.setObjectName("StepBadge")
        badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setMaximumWidth(110)
        root.addWidget(badge)

        title = QLabel("Trouver des clips")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        sub = QLabel(
            "Écrivez le nom d’un streamer (ex. xQc), cliquez Rechercher, "
            "puis cochez les clips qui vous plaisent."
        )
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(sub)

        row = QHBoxLayout()
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("Nom du streamer, ou collez son lien Twitch…")
        self.query_edit.returnPressed.connect(self._on_search)
        row.addWidget(self.query_edit, stretch=3)

        self.mode_combo = MenuCombo()
        self.mode_combo.addItem("Streamer", "streamer")
        self.mode_combo.addItem("Jeu vidéo", "game")
        self.mode_combo.setMinimumWidth(140)
        row.addWidget(self.mode_combo)

        self.period_combo = MenuCombo()
        self.period_combo.addItem("Dernières 24 h", "24h")
        self.period_combo.addItem("7 derniers jours", "7d")
        self.period_combo.addItem("30 derniers jours", "30d")
        self.period_combo.setCurrentIndex(1)
        self.period_combo.setMinimumWidth(170)
        row.addWidget(self.period_combo)
        root.addLayout(row)

        follow_row = QHBoxLayout()
        self.followed_check = QCheckBox("Chercher dans les streamers que je suis")
        self.followed_check.setToolTip(
            "Parcourt la liste de l’Accueil (streamers suivis) au lieu d’un seul nom."
        )
        self.followed_check.toggled.connect(self._on_followed_toggled)
        follow_row.addWidget(self.followed_check)
        self.followed_hint = QLabel("")
        self.followed_hint.setObjectName("PageSubtitle")
        follow_row.addWidget(self.followed_hint, stretch=1)
        root.addLayout(follow_row)

        row2 = QHBoxLayout()
        count_lbl = QLabel("Nombre de clips :")
        count_lbl.setObjectName("PageSubtitle")
        row2.addWidget(count_lbl)

        self.max_spin = QSpinBox()
        style_spinbox(self.max_spin)
        self.max_spin.setRange(1, 500)
        self.max_spin.setValue(100)
        self.max_spin.setSingleStep(10)
        self.max_spin.setMinimumWidth(110)
        self.max_spin.setToolTip(
            "Jusqu’à 500. Twitch envoie 100 par page — l’appli enchaîne les pages."
        )
        row2.addWidget(self.max_spin)

        hint = QLabel("(ex. 100, 200… max 500)")
        hint.setObjectName("PageSubtitle")
        row2.addWidget(hint)
        row2.addStretch(1)

        self.search_btn = QPushButton("Rechercher")
        self.search_btn.setObjectName("BigAction")
        self.search_btn.clicked.connect(self._on_search)
        row2.addWidget(self.search_btn)
        root.addLayout(row2)

        tools = QHBoxLayout()
        self.select_all_btn = QPushButton("Tout cocher")
        self.select_all_btn.setObjectName("SecondaryButton")
        self.select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        tools.addWidget(self.select_all_btn)

        self.clear_btn = QPushButton("Tout décocher")
        self.clear_btn.setObjectName("SecondaryButton")
        self.clear_btn.clicked.connect(lambda: self._set_all_checked(False))
        tools.addWidget(self.clear_btn)
        tools.addStretch(1)
        self.status_label = QLabel("Aucun résultat pour le moment")
        self.status_label.setObjectName("PageSubtitle")
        tools.addWidget(self.status_label)
        root.addLayout(tools)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("ClipList")
        self.list_widget.setSpacing(0)
        self.list_widget.setUniformItemSizes(False)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        root.addWidget(self.list_widget, stretch=1)

        bottom = QHBoxLayout()
        tip = QLabel("Astuce : on ignore automatiquement les clips déjà traités.")
        tip.setObjectName("PageSubtitle")
        bottom.addWidget(tip)
        bottom.addStretch(1)
        self.send_btn = QPushButton("Étape suivante : créer la vidéo →")
        self.send_btn.setObjectName("BigAction")
        self.send_btn.clicked.connect(self._send_selected)
        bottom.addWidget(self.send_btn)
        root.addLayout(bottom)

    def _on_search(self) -> None:
        if not self._twitch:
            return
        if not self._twitch.is_configured():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Clés Twitch manquantes")
            box.setText(
                "Il faut d’abord coller vos clés Twitch dans Réglages "
                "(Client ID et Client Secret).\n\n"
                "Sans ça, l’appli ne peut pas chercher de clips."
            )
            box.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Open
            )
            open_btn = box.button(QMessageBox.StandardButton.Open)
            open_btn.setText("Ouvrir les réglages")
            if box.exec() == QMessageBox.StandardButton.Open:
                self.go_settings.emit()
            return

        use_followed = self.followed_check.isChecked()
        streamers = self._followed_streamers() if use_followed else []
        query = self.query_edit.text().strip()

        if use_followed and not streamers:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle("Aucun streamer suivi")
            box.setText(
                "Ajoutez d’abord des streamers sur l’Accueil "
                "(« Streamers que je suis »), puis revenez ici."
            )
            box.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Open
            )
            open_btn = box.button(QMessageBox.StandardButton.Open)
            open_btn.setText("Aller à l’Accueil")
            if box.exec() == QMessageBox.StandardButton.Open:
                self.go_home.emit()
            return

        if not use_followed and not query:
            QMessageBox.information(
                self,
                "Nom manquant",
                "Écrivez le nom d’un streamer, par exemple : xQc\n"
                "— ou cochez « Chercher dans les streamers que je suis ».",
            )
            return
        if self._worker and self._worker.isRunning():
            return

        self.search_btn.setEnabled(False)
        self.status_label.setText("Recherche en cours… un instant")
        self._worker = SearchClipsWorker(
            self._twitch,
            query=query,
            period=self.period_combo.currentData(),
            max_clips=self.max_spin.value(),
            max_duration=60.0,
            is_game=(
                False
                if use_followed
                else self.mode_combo.currentData() == "game"
            ),
            streamers=streamers if use_followed else None,
        )
        self._worker.finished_ok.connect(self._on_results)
        self._worker.failed.connect(self._on_error)
        self._worker.progress.connect(lambda m: self.status_label.setText(m))
        self._worker.start()

    def _followed_streamers(self) -> list[str]:
        if not self._config:
            return []
        raw = self._config.get("followed_streamers", default=[]) or []
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            login = str(item).strip().lstrip("@").lower()
            if login and login not in seen:
                seen.add(login)
                out.append(login)
        return out

    def _refresh_followed_label(self) -> None:
        n = len(self._followed_streamers())
        if n:
            self.followed_hint.setText(f"({n} dans votre liste)")
        else:
            self.followed_hint.setText("(liste vide — ajoutez-en sur l’Accueil)")

    def _on_followed_toggled(self, checked: bool) -> None:
        self._refresh_followed_label()
        self.query_edit.setEnabled(not checked)
        self.mode_combo.setEnabled(not checked)
        if checked:
            self.query_edit.setPlaceholderText(
                "Inutile — recherche sur vos streamers suivis"
            )
        else:
            self.query_edit.setPlaceholderText(
                "Nom du streamer, ou collez son lien Twitch…"
            )

    def refresh(self) -> None:
        """Called when the page is shown — refresh followed count."""
        self._refresh_followed_label()

    def _on_results(self, clips: list) -> None:
        self.search_btn.setEnabled(True)
        filtered: list[Clip] = []
        skipped = 0
        for clip in clips:
            if self._db and self._db.is_clip_processed(clip.id):
                skipped += 1
                continue
            filtered.append(clip)
        self._clips = filtered
        self._rows.clear()
        self.list_widget.clear()
        for clip in filtered:
            item = QListWidgetItem(self.list_widget)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setData(Qt.ItemDataRole.UserRole, clip.id)
            row = ClipRowWidget(clip)
            item.setSizeHint(row.sizeHint().expandedTo(QSize(0, 124)))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)
            self._rows[clip.id] = row
            self._load_thumb(row, clip.thumbnail_url)

        msg = f"{len(filtered)} clip(s) trouvé(s)"
        if skipped:
            msg += f" · {skipped} déjà faits (ignorés)"
        if not filtered:
            msg = "Aucun clip trouvé. Essayez une autre période ou un autre nom."
        self.status_label.setText(msg)
        self.log_requested.emit(f"Recherche: {msg}")

    def _load_thumb(self, row: ClipRowWidget, url: str) -> None:
        if not url:
            return
        url = url.replace("%{width}", "320").replace("%{height}", "180")
        reply = self._net.get(QNetworkRequest(QUrl(url)))

        def done() -> None:
            data = reply.readAll()
            pix = QPixmap()
            if pix.loadFromData(data):
                row.set_thumbnail(pix)
            reply.deleteLater()

        reply.finished.connect(done)

    def _on_error(self, message: str) -> None:
        self.search_btn.setEnabled(True)
        self.status_label.setText("La recherche a échoué")
        QMessageBox.critical(
            self,
            "Erreur Twitch",
            "Impossible de récupérer les clips.\n\n"
            f"Détail : {message}\n\n"
            "Vérifiez vos clés Twitch dans Réglages.",
        )
        self.log_requested.emit(f"Erreur recherche: {message}")

    def _set_all_checked(self, checked: bool) -> None:
        for row in self._rows.values():
            row.set_checked(checked)

    def _send_selected(self) -> None:
        selected = [
            c for c in self._clips if self._rows.get(c.id) and self._rows[c.id].is_checked()
        ]
        if not selected:
            QMessageBox.information(
                self,
                "Aucune sélection",
                "Cochez au moins une case à gauche d’un clip, puis réessayez.",
            )
            return
        self.clips_selected.emit(selected)
