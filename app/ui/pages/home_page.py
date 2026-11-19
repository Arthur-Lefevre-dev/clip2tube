"""Home / onboarding page — checklist, followed streamers CRUD, 3-step path."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.twitch import normalize_twitch_query
from app.utils.config import save_config


def _normalize_login(raw: str) -> str:
    """Accept a Twitch login or channel URL and return a clean login."""
    # URLs like https://www.twitch.tv/xqc → xqc
    extracted = normalize_twitch_query(raw)
    login = (extracted or "").strip().lstrip("@").lower()
    # Twitch login: letters, digits, underscore only
    return "".join(ch for ch in login if ch.isalnum() or ch == "_")


class HomePage(QWidget):
    """Landing screen: setup checklist, streamers list, next actions."""

    go_to = Signal(str)  # nav id
    streamers_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._twitch = None
        self._youtube = None
        self._config = None
        self._build()

    def bind(self, config, twitch, youtube) -> None:
        self._config = config
        self._twitch = twitch
        self._youtube = youtube
        self.refresh()

    def refresh(self) -> None:
        twitch_ok = bool(self._twitch and self._twitch.is_configured())
        youtube_ok = bool(self._youtube and self._youtube.is_connected())
        ffmpeg_hint = ""
        if self._config:
            from app.utils.ffmpeg import find_ffmpeg

            found = find_ffmpeg(str(self._config.get("ffmpeg_path", default="") or ""))
            ffmpeg_ok = found is not None
            ffmpeg_hint = str(found) if found else ""
        else:
            ffmpeg_ok = False

        self.twitch_status.setText("Prêt ✓" if twitch_ok else "À configurer")
        self.twitch_status.setObjectName("StatusOk" if twitch_ok else "StatusKo")
        self._repolish(self.twitch_status)

        self.ffmpeg_status.setText("Trouvé ✓" if ffmpeg_ok else "À installer / indiquer")
        self.ffmpeg_status.setObjectName("StatusOk" if ffmpeg_ok else "StatusKo")
        self._repolish(self.ffmpeg_status)
        self.ffmpeg_detail.setText(ffmpeg_hint or "Nécessaire pour créer les vidéos")

        self.youtube_status.setText(
            "Connecté ✓" if youtube_ok else "Optionnel pour l’instant"
        )
        self.youtube_status.setObjectName("StatusOk" if youtube_ok else "StatusKo")
        self._repolish(self.youtube_status)

        if twitch_ok and ffmpeg_ok:
            self.hero_hint.setText(
                "Ajoutez vos streamers ci-dessous, puis cherchez des clips."
            )
        elif not twitch_ok:
            self.hero_hint.setText(
                "Commencez par ouvrir Réglages et coller vos clés Twitch (2 cases)."
            )
        else:
            self.hero_hint.setText(
                "Il manque FFmpeg : dans Réglages, cliquez « Détecter » ou indiquez le chemin."
            )

        self._reload_streamers_list()

    def _repolish(self, widget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(36, 30, 36, 36)
        root.setSpacing(22)

        # —— Hero ——
        hero = QFrame()
        hero.setObjectName("HomeHero")
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(22, 20, 22, 20)
        hero_lay.setSpacing(8)

        eyebrow = QLabel("Clip2Tube")
        eyebrow.setObjectName("HomeEyebrow")
        hero_lay.addWidget(eyebrow)

        title = QLabel("Transformez des clips Twitch en vidéos verticales")
        title.setObjectName("PageTitle")
        title.setWordWrap(True)
        hero_lay.addWidget(title)

        self.hero_hint = QLabel(
            "Cette appli télécharge un clip, le met en 9:16, et prépare YouTube / TikTok."
        )
        self.hero_hint.setObjectName("PageSubtitle")
        self.hero_hint.setWordWrap(True)
        hero_lay.addWidget(self.hero_hint)
        root.addWidget(hero)

        # —— Checklist + Streamers side by side ——
        mid = QHBoxLayout()
        mid.setSpacing(16)
        mid.addWidget(self._build_checklist_card(), stretch=1)
        mid.addWidget(self._build_streamers_card(), stretch=1)
        root.addLayout(mid)

        # —— Steps ——
        steps_head = QHBoxLayout()
        steps_title = QLabel("Ensuite, 3 gestes simples")
        steps_title.setObjectName("HomeSectionTitle")
        steps_head.addWidget(steps_title)
        steps_head.addStretch(1)
        root.addLayout(steps_head)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        cards.addWidget(
            self._action_card(
                "1",
                "Trouver des clips",
                "Tapez un streamer (ou partez de votre liste), puis cochez les moments.",
                "Chercher des clips",
                "clips",
            )
        )
        cards.addWidget(
            self._action_card(
                "2",
                "Créer la vidéo",
                "Choisissez le style, éventuellement la zone du visage, puis lancez.",
                "Créer ma vidéo",
                "process",
            )
        )
        cards.addWidget(
            self._action_card(
                "3",
                "Publier",
                "Vérifiez le résultat, puis envoyez sur YouTube (ou exportez pour TikTok).",
                "Voir mes vidéos",
                "queue",
            )
        )
        root.addLayout(cards)
        root.addStretch(1)

    def _build_checklist_card(self) -> QFrame:
        check = QFrame()
        check.setObjectName("HelpCard")
        check.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(check)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        head = QLabel("Avant de commencer")
        head.setObjectName("HomeSectionTitle")
        lay.addWidget(head)

        lay.addLayout(self._status_row("1. Clés Twitch", "twitch_status"))
        lay.addLayout(self._status_row("2. FFmpeg (outil vidéo)", "ffmpeg_status"))
        self.ffmpeg_detail = QLabel("")
        self.ffmpeg_detail.setObjectName("PageSubtitle")
        self.ffmpeg_detail.setWordWrap(True)
        lay.addWidget(self.ffmpeg_detail)
        lay.addLayout(self._status_row("3. Compte YouTube", "youtube_status"))

        lay.addStretch(1)
        settings_btn = QPushButton("Ouvrir les réglages")
        settings_btn.setObjectName("SecondaryButton")
        settings_btn.clicked.connect(lambda: self.go_to.emit("settings"))
        lay.addWidget(settings_btn)
        return check

    def _build_streamers_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("HelpCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        head_row = QHBoxLayout()
        head = QLabel("Streamers que je suis")
        head.setObjectName("HomeSectionTitle")
        head_row.addWidget(head)
        self.streamer_count = QLabel("0")
        self.streamer_count.setObjectName("StreamerCount")
        head_row.addStretch(1)
        head_row.addWidget(self.streamer_count)
        lay.addLayout(head_row)

        tip = QLabel(
            "Liste utilisée par le mode automatique. "
            "Pseudo (xqc) ou lien de chaîne (twitch.tv/xqc) — les deux marchent."
        )
        tip.setObjectName("PageSubtitle")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.streamer_input = QLineEdit()
        self.streamer_input.setPlaceholderText("pseudo ou lien Twitch…")
        self.streamer_input.returnPressed.connect(self._add_streamer)
        add_row.addWidget(self.streamer_input, stretch=1)
        add_btn = QPushButton("Ajouter")
        add_btn.clicked.connect(self._add_streamer)
        add_row.addWidget(add_btn)
        lay.addLayout(add_row)

        self.streamers_list = QListWidget()
        self.streamers_list.setMinimumHeight(160)
        self.streamers_list.setAlternatingRowColors(False)
        self.streamers_list.itemDoubleClicked.connect(self._edit_streamer)
        lay.addWidget(self.streamers_list, stretch=1)

        self.empty_streamers = QLabel("Aucun streamer pour l’instant — ajoutez-en un ci-dessus.")
        self.empty_streamers.setObjectName("EmptyHint")
        self.empty_streamers.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_streamers.setWordWrap(True)
        lay.addWidget(self.empty_streamers)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        edit_btn = QPushButton("Modifier")
        edit_btn.setObjectName("SecondaryButton")
        edit_btn.clicked.connect(self._edit_selected)
        del_btn = QPushButton("Supprimer")
        del_btn.setObjectName("DangerButton")
        del_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton("Tout vider")
        clear_btn.setObjectName("SecondaryButton")
        clear_btn.clicked.connect(self._clear_all)
        actions.addWidget(edit_btn)
        actions.addWidget(del_btn)
        actions.addWidget(clear_btn)
        actions.addStretch(1)
        lay.addLayout(actions)
        return card

    def _status_row(self, label: str, attr: str) -> QHBoxLayout:
        row = QHBoxLayout()
        name = QLabel(label)
        name.setObjectName("PageSubtitle")
        status = QLabel("…")
        setattr(self, attr, status)
        row.addWidget(name)
        row.addStretch(1)
        row.addWidget(status)
        return row

    def _action_card(
        self, step: str, title: str, body: str, cta: str, nav_id: str
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("HomeCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)

        badge = QLabel(f"Étape {step}")
        badge.setObjectName("StepBadge")
        badge.setMaximumWidth(100)
        lay.addWidget(badge)

        t = QLabel(title)
        t.setObjectName("HomeCardTitle")
        t.setWordWrap(True)
        lay.addWidget(t)

        b = QLabel(body)
        b.setObjectName("HomeCardBody")
        b.setWordWrap(True)
        lay.addWidget(b)
        lay.addStretch(1)

        btn = QPushButton(cta)
        btn.setObjectName("BigAction")
        btn.clicked.connect(lambda: self.go_to.emit(nav_id))
        lay.addWidget(btn)
        return card

    # —— Streamers CRUD ——

    def _current_streamers(self) -> list[str]:
        if not self._config:
            return []
        raw = self._config.get("followed_streamers", default=[]) or []
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            login = _normalize_login(str(item))
            if login and login not in seen:
                seen.add(login)
                out.append(login)
        return out

    def _persist_streamers(self, streamers: list[str]) -> None:
        if not self._config:
            return
        self._config.set("followed_streamers", streamers)
        save_config(self._config)
        self._reload_streamers_list()
        self.streamers_changed.emit()

    def _reload_streamers_list(self) -> None:
        streamers = self._current_streamers()
        self.streamers_list.clear()
        for login in streamers:
            item = QListWidgetItem(login)
            item.setToolTip(f"twitch.tv/{login}")
            self.streamers_list.addItem(item)
        n = len(streamers)
        self.streamer_count.setText(f"{n} streamer{'s' if n != 1 else ''}")
        self.empty_streamers.setVisible(n == 0)
        self.streamers_list.setVisible(n > 0)

    def _add_streamer(self) -> None:
        login = _normalize_login(self.streamer_input.text())
        if not login:
            QMessageBox.information(
                self,
                "Pseudo manquant",
                "Entrez un pseudo (ex. xqc) ou un lien twitch.tv/…",
            )
            return
        streamers = self._current_streamers()
        if login in streamers:
            QMessageBox.information(
                self, "Déjà dans la liste", f"{login} est déjà suivi."
            )
            return
        streamers.append(login)
        self.streamer_input.clear()
        self._persist_streamers(streamers)

    def _selected_login(self) -> str | None:
        item = self.streamers_list.currentItem()
        if not item:
            return None
        return item.text().strip()

    def _edit_selected(self) -> None:
        login = self._selected_login()
        if not login:
            QMessageBox.information(
                self, "Aucune sélection", "Cliquez d’abord un streamer dans la liste."
            )
            return
        self._edit_streamer_login(login)

    def _edit_streamer(self, item: QListWidgetItem) -> None:
        if item:
            self._edit_streamer_login(item.text().strip())

    def _edit_streamer_login(self, old: str) -> None:
        new_raw, ok = QInputDialog.getText(
            self,
            "Modifier le streamer",
            "Nouveau pseudo ou lien Twitch :",
            text=old,
        )
        if not ok:
            return
        new = _normalize_login(new_raw)
        if not new:
            QMessageBox.warning(
                self, "Pseudo invalide", "Le pseudo ne peut pas être vide."
            )
            return
        streamers = self._current_streamers()
        if old not in streamers:
            return
        if new != old and new in streamers:
            QMessageBox.information(
                self, "Déjà dans la liste", f"{new} est déjà suivi."
            )
            return
        idx = streamers.index(old)
        streamers[idx] = new
        self._persist_streamers(streamers)

    def _remove_selected(self) -> None:
        login = self._selected_login()
        if not login:
            QMessageBox.information(
                self, "Aucune sélection", "Cliquez d’abord un streamer dans la liste."
            )
            return
        reply = QMessageBox.question(
            self,
            "Supprimer",
            f"Retirer {login} de la liste ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        streamers = [s for s in self._current_streamers() if s != login]
        self._persist_streamers(streamers)

    def _clear_all(self) -> None:
        if not self._current_streamers():
            return
        reply = QMessageBox.question(
            self,
            "Tout vider",
            "Supprimer tous les streamers suivis ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._persist_streamers([])
