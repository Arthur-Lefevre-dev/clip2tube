"""Friendly home / onboarding page with a 3-step path."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class HomePage(QWidget):
    """Landing screen: setup checklist + big next actions."""

    go_to = Signal(str)  # nav id

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

        self.ffmpeg_status.setText(
            f"Trouvé ✓" if ffmpeg_ok else "À installer / indiquer"
        )
        self.ffmpeg_status.setObjectName("StatusOk" if ffmpeg_ok else "StatusKo")
        self._repolish(self.ffmpeg_status)
        self.ffmpeg_detail.setText(ffmpeg_hint or "Nécessaire pour créer les vidéos")

        self.youtube_status.setText("Connecté ✓" if youtube_ok else "Optionnel pour l’instant")
        self.youtube_status.setObjectName("StatusOk" if youtube_ok else "StatusKo")
        self._repolish(self.youtube_status)

        if twitch_ok and ffmpeg_ok:
            self.hero_hint.setText(
                "Tout est prêt pour chercher des clips et créer une vidéo."
            )
        elif not twitch_ok:
            self.hero_hint.setText(
                "Commencez par ouvrir Réglages et coller vos clés Twitch (2 cases)."
            )
        else:
            self.hero_hint.setText(
                "Il manque FFmpeg : dans Réglages, cliquez « Détecter » ou indiquez le chemin."
            )

    def _repolish(self, widget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        title = QLabel("Bienvenue dans Clip2Tube")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        self.hero_hint = QLabel(
            "Cette appli transforme un clip Twitch en vidéo verticale pour YouTube / TikTok."
        )
        self.hero_hint.setObjectName("PageSubtitle")
        self.hero_hint.setWordWrap(True)
        root.addWidget(self.hero_hint)

        # Checklist
        check = QFrame()
        check.setObjectName("HelpCard")
        check_lay = QVBoxLayout(check)
        check_title = QLabel("Avant de commencer — checklist")
        check_title.setObjectName("HomeCardTitle")
        check_lay.addWidget(check_title)

        row1 = self._status_row("1. Clés Twitch", "twitch_status")
        check_lay.addLayout(row1)
        row2 = self._status_row("2. FFmpeg (outil vidéo)", "ffmpeg_status")
        check_lay.addLayout(row2)
        self.ffmpeg_detail = QLabel("")
        self.ffmpeg_detail.setObjectName("PageSubtitle")
        check_lay.addWidget(self.ffmpeg_detail)
        row3 = self._status_row("3. Compte YouTube", "youtube_status")
        check_lay.addLayout(row3)

        settings_btn = QPushButton("Ouvrir les réglages")
        settings_btn.setObjectName("SecondaryButton")
        settings_btn.clicked.connect(lambda: self.go_to.emit("settings"))
        check_lay.addWidget(settings_btn)
        root.addWidget(check)

        # Steps
        steps_title = QLabel("Ensuite, 3 gestes simples")
        steps_title.setObjectName("HomeCardTitle")
        root.addWidget(steps_title)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        cards.addWidget(
            self._action_card(
                "1",
                "Trouver des clips",
                "Tapez le nom d’un streamer, puis cochez les moments amusants.",
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
