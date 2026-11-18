"""Clip search page — plain-language UX."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QComboBox,
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
from app.ui.workers import SearchClipsWorker


class ClipsPage(QWidget):
    clips_selected = Signal(list)
    log_requested = Signal(str)
    go_settings = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._twitch = None
        self._db = None
        self._worker: Optional[SearchClipsWorker] = None
        self._clips: list[Clip] = []
        self._net = QNetworkAccessManager(self)
        self._build()

    def bind(self, twitch, database) -> None:
        self._twitch = twitch
        self._db = database

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(14)

        badge = QLabel("Étape 1")
        badge.setObjectName("StepBadge")
        badge.setMaximumWidth(90)
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

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Streamer", "streamer")
        self.mode_combo.addItem("Jeu vidéo", "game")
        self.mode_combo.setMinimumWidth(130)
        row.addWidget(self.mode_combo)

        self.period_combo = QComboBox()
        self.period_combo.addItem("Dernières 24 h", "24h")
        self.period_combo.addItem("7 derniers jours", "7d")
        self.period_combo.addItem("30 derniers jours", "30d")
        self.period_combo.setCurrentIndex(1)
        self.period_combo.setMinimumWidth(160)
        row.addWidget(self.period_combo)
        root.addLayout(row)

        row2 = QHBoxLayout()
        count_lbl = QLabel("Nombre de clips :")
        count_lbl.setObjectName("PageSubtitle")
        row2.addWidget(count_lbl)

        self.max_spin = QSpinBox()
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
        self.list_widget.setIconSize(QSize(180, 100))
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

        query = self.query_edit.text().strip()
        if not query:
            QMessageBox.information(
                self,
                "Nom manquant",
                "Écrivez le nom d’un streamer, par exemple : xQc",
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
            is_game=self.mode_combo.currentData() == "game",
        )
        self._worker.finished_ok.connect(self._on_results)
        self._worker.failed.connect(self._on_error)
        self._worker.progress.connect(lambda m: self.status_label.setText(m))
        self._worker.start()

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
        self.list_widget.clear()
        for clip in filtered:
            item = QListWidgetItem()
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            created = (
                clip.created_at.strftime("%d/%m/%Y %H:%M") if clip.created_at else "—"
            )
            item.setText(
                f"{clip.title}\n"
                f"{clip.broadcaster_name} · {clip.views_label} vues · "
                f"{clip.duration_label} · {created}"
            )
            item.setData(Qt.ItemDataRole.UserRole, clip.id)
            self.list_widget.addItem(item)
            self._load_thumb(item, clip.thumbnail_url)

        msg = f"{len(filtered)} clip(s) trouvé(s)"
        if skipped:
            msg += f" · {skipped} déjà faits (ignorés)"
        if not filtered:
            msg = "Aucun clip trouvé. Essayez une autre période ou un autre nom."
        self.status_label.setText(msg)
        self.log_requested.emit(f"Recherche: {msg}")

    def _load_thumb(self, item: QListWidgetItem, url: str) -> None:
        if not url:
            return
        url = url.replace("%{width}", "320").replace("%{height}", "180")
        reply = self._net.get(QNetworkRequest(QUrl(url)))

        def done() -> None:
            data = reply.readAll()
            pix = QPixmap()
            if pix.loadFromData(data):
                item.setIcon(
                    pix.scaled(
                        180,
                        100,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
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
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(state)

    def _send_selected(self) -> None:
        ids = set()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.add(item.data(Qt.ItemDataRole.UserRole))
        selected = [c for c in self._clips if c.id in ids]
        if not selected:
            QMessageBox.information(
                self,
                "Aucune sélection",
                "Cochez au moins une case à gauche de un clip, puis réessayez.",
            )
            return
        self.clips_selected.emit(selected)
