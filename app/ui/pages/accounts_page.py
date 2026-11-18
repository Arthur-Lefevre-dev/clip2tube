"""Connected accounts — YouTube OAuth and TikTok / export."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.workers import OAuthWorker


class AccountsPage(QWidget):
    log_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._youtube = None
        self._tiktok = None
        self._worker: Optional[OAuthWorker] = None
        self._build()

    def bind(self, youtube, tiktok) -> None:
        self._youtube = youtube
        self._tiktok = tiktok
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("Comptes de publication")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        sub = QLabel(
            "Pour envoyer une vidéo sur YouTube, connectez votre compte une fois. "
            "Une page Google s’ouvrira dans votre navigateur — c’est normal. "
            "Pour TikTok, sans compte API on exporte un fichier prêt à uploader à la main."
        )
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # YouTube
        yt = QGroupBox("YouTube")
        yt_lay = QVBoxLayout(yt)
        self.yt_status = QLabel("Pas encore connecté")
        yt_lay.addWidget(self.yt_status)
        row = QHBoxLayout()
        self.yt_connect = QPushButton("Connecter mon YouTube")
        self.yt_connect.setObjectName("BigAction")
        self.yt_connect.clicked.connect(self._connect_youtube)
        self.yt_disconnect = QPushButton("Déconnecter")
        self.yt_disconnect.setObjectName("SecondaryButton")
        self.yt_disconnect.clicked.connect(self._disconnect_youtube)
        row.addWidget(self.yt_connect)
        row.addWidget(self.yt_disconnect)
        row.addStretch(1)
        yt_lay.addLayout(row)
        root.addWidget(yt)

        # TikTok
        tt = QGroupBox("TikTok")
        tt_lay = QVBoxLayout(tt)
        self.tt_status = QLabel("Mode simple : export dans un dossier")
        tt_lay.addWidget(self.tt_status)

        row2 = QHBoxLayout()
        self.tt_connect = QPushButton("Connexion TikTok (avancé)")
        self.tt_connect.setObjectName("SecondaryButton")
        self.tt_connect.clicked.connect(self._connect_tiktok)
        self.tt_disconnect = QPushButton("Déconnecter")
        self.tt_disconnect.setObjectName("SecondaryButton")
        self.tt_disconnect.clicked.connect(self._disconnect_tiktok)
        row2.addWidget(self.tt_connect)
        row2.addWidget(self.tt_disconnect)
        row2.addStretch(1)
        tt_lay.addLayout(row2)

        code_row = QHBoxLayout()
        self.tt_code = QLineEdit()
        self.tt_code.setPlaceholderText("Si TikTok vous donne un code, collez-le ici…")
        code_btn = QPushButton("Valider le code")
        code_btn.setObjectName("SecondaryButton")
        code_btn.clicked.connect(self._complete_tiktok)
        code_row.addWidget(self.tt_code, stretch=1)
        code_row.addWidget(code_btn)
        tt_lay.addLayout(code_row)

        hint = QLabel(
            "Sans connexion TikTok, les vidéos vont dans le dossier "
            "output/tiktok_export/ — vous pourrez les publier vous-même sur TikTok."
        )
        hint.setObjectName("PageSubtitle")
        hint.setWordWrap(True)
        tt_lay.addWidget(hint)
        root.addWidget(tt)

        root.addStretch(1)

    def refresh(self) -> None:
        if self._youtube and self._youtube.is_connected():
            self.yt_status.setText("Connecté ✓")
        else:
            self.yt_status.setText("Non connecté")

        if self._tiktok and self._tiktok.is_connected():
            self.tt_status.setText("Connecté ✓")
        elif self._tiktok and self._tiktok.is_api_available():
            self.tt_status.setText("Clés présentes — OAuth requis (ou mode export)")
        else:
            self.tt_status.setText("Mode export (pas de clés API TikTok)")

    def _connect_youtube(self) -> None:
        if not self._youtube:
            return
        if self._worker and self._worker.isRunning():
            return
        self.yt_connect.setEnabled(False)
        self._worker = OAuthWorker(self._youtube.connect)
        self._worker.finished_ok.connect(self._on_yt_ok)
        self._worker.failed.connect(self._on_yt_fail)
        self._worker.start()
        self.log_requested.emit("OAuth YouTube démarré…")

    def _on_yt_ok(self, name: str) -> None:
        self.yt_connect.setEnabled(True)
        self.refresh()
        QMessageBox.information(self, "YouTube", f"Connecté : {name}")
        self.log_requested.emit(f"YouTube connecté: {name}")

    def _on_yt_fail(self, message: str) -> None:
        self.yt_connect.setEnabled(True)
        QMessageBox.warning(self, "YouTube", message)
        self.log_requested.emit(f"YouTube OAuth: {message}")

    def _disconnect_youtube(self) -> None:
        if self._youtube:
            self._youtube.disconnect()
            self.refresh()
            self.log_requested.emit("YouTube déconnecté")

    def _connect_tiktok(self) -> None:
        if not self._tiktok:
            return
        try:
            self._tiktok.connect()
        except Exception as exc:
            QMessageBox.information(self, "TikTok", str(exc))
            self.log_requested.emit(str(exc))

    def _complete_tiktok(self) -> None:
        if not self._tiktok:
            return
        try:
            name = self._tiktok.complete_oauth(self.tt_code.text())
            self.refresh()
            QMessageBox.information(self, "TikTok", f"Connecté : {name}")
        except Exception as exc:
            QMessageBox.warning(self, "TikTok", str(exc))

    def _disconnect_tiktok(self) -> None:
        if self._tiktok:
            self._tiktok.disconnect()
            self.refresh()
