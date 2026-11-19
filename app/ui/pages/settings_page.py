"""Application settings form bound to config.json."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QDoubleSpinBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from app.ui.theme import style_spinbox
from app.ui.widgets.menu_combo import MenuCombo
from app.utils.config import save_config
from app.utils.ffmpeg import find_ffmpeg
from app.utils.paths import get_app_root


class SettingsPage(QWidget):
    log_requested = Signal(str)
    saved = Signal()
    check_updates_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._config = None
        self._build()

    def bind(self, config) -> None:
        self._config = config
        self._load()

    def refresh_from_config(self) -> None:
        """Reload form fields from disk-backed config (e.g. after Accueil CRUD)."""
        self._load()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel("Réglages")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        help_lbl = QLabel(
            "Remplissez surtout Twitch et FFmpeg. "
            "Les autres cases sont pour publier plus tard. "
            "Puis cliquez « Enregistrer » en bas."
        )
        help_lbl.setObjectName("PageSubtitle")
        help_lbl.setWordWrap(True)
        root.addWidget(help_lbl)

        # Twitch
        twitch = QGroupBox("Twitch (obligatoire pour chercher des clips)")
        tf = QFormLayout(twitch)
        self.twitch_id = QLineEdit()
        self.twitch_id.setPlaceholderText("Collez le Client ID ici")
        self.twitch_secret = QLineEdit()
        self.twitch_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.twitch_secret.setPlaceholderText("Collez le Client Secret ici")
        tf.addRow("Client ID", self.twitch_id)
        tf.addRow("Client Secret", self.twitch_secret)
        tip_tw = QLabel("Obtenez-les sur dev.twitch.tv/console (gratuit).")
        tip_tw.setObjectName("PageSubtitle")
        tf.addRow(tip_tw)
        root.addWidget(twitch)

        # Google
        google = QGroupBox("YouTube / Google (pour publier)")
        gf = QFormLayout(google)
        self.google_id = QLineEdit()
        self.google_secret = QLineEdit()
        self.google_secret.setEchoMode(QLineEdit.EchoMode.Password)
        gf.addRow("Client ID Google", self.google_id)
        gf.addRow("Client Secret Google", self.google_secret)
        root.addWidget(google)

        # TikTok
        tiktok = QGroupBox("TikTok (optionnel — sinon export manuel)")
        tk = QFormLayout(tiktok)
        self.tiktok_key = QLineEdit()
        self.tiktok_secret = QLineEdit()
        self.tiktok_secret.setEchoMode(QLineEdit.EchoMode.Password)
        tk.addRow("Client Key", self.tiktok_key)
        tk.addRow("Client Secret", self.tiktok_secret)
        root.addWidget(tiktok)

        # Paths
        paths = QGroupBox("Outil vidéo FFmpeg (obligatoire)")
        pf = QFormLayout(paths)
        ffmpeg_row = QHBoxLayout()
        self.ffmpeg_path = QLineEdit()
        self.ffmpeg_path.setPlaceholderText("Chemin vers ffmpeg.exe")
        browse_ff = QPushButton("Parcourir…")
        browse_ff.setObjectName("SecondaryButton")
        browse_ff.clicked.connect(self._browse_ffmpeg)
        detect = QPushButton("Détecter automatiquement")
        detect.setObjectName("SecondaryButton")
        detect.clicked.connect(self._detect_ffmpeg)
        ffmpeg_row.addWidget(self.ffmpeg_path, stretch=1)
        ffmpeg_row.addWidget(browse_ff)
        ffmpeg_row.addWidget(detect)
        pf.addRow("FFmpeg", ffmpeg_row)

        out_row = QHBoxLayout()
        self.output_dir = QLineEdit()
        browse_out = QPushButton("…")
        browse_out.setObjectName("SecondaryButton")
        browse_out.setFixedWidth(36)
        browse_out.clicked.connect(self._browse_output)
        out_row.addWidget(self.output_dir, stretch=1)
        out_row.addWidget(browse_out)
        pf.addRow("Dossier sortie", out_row)

        self.quality = MenuCombo()
        for q in ("high", "medium", "low"):
            self.quality.addItem(q, q)
        pf.addRow("Qualité", self.quality)
        root.addWidget(paths)

        # Streamers (also editable on Accueil — kept here for bulk paste)
        streamers = QGroupBox("Streamers suivis (auto-pilote)")
        sf = QVBoxLayout(streamers)
        hint = QLabel(
            "Astuce : vous pouvez aussi les gérer un par un sur l’Accueil. "
            "Ici, un pseudo par ligne (pratique pour coller une liste)."
        )
        hint.setWordWrap(True)
        hint.setObjectName("PageSubtitle")
        sf.addWidget(hint)
        self.streamers_edit = QTextEdit()
        self.streamers_edit.setPlaceholderText(
            "un pseudo par ligne\nex:\nxqc\npokimane"
        )
        self.streamers_edit.setFixedHeight(100)
        sf.addWidget(self.streamers_edit)
        root.addWidget(streamers)

        # Defaults / templates
        defaults = QGroupBox("Modèles & sous-titres")
        df = QFormLayout(defaults)
        self.yt_title_tpl = QLineEdit()
        self.yt_desc_tpl = QTextEdit()
        self.yt_desc_tpl.setFixedHeight(70)
        self.tt_tpl = QLineEdit()
        df.addRow("Titre YouTube", self.yt_title_tpl)
        df.addRow("Description YT", self.yt_desc_tpl)
        df.addRow("Légende TikTok", self.tt_tpl)

        self.title_font = QLineEdit("Arial")
        self.title_color = QLineEdit("#FFFFFF")
        self.sub_font = QLineEdit("Arial")
        self.sub_color = QLineEdit("#FFFFFF")
        df.addRow("Police titre", self.title_font)
        df.addRow("Couleur titre", self.title_color)
        df.addRow("Police sous-titres", self.sub_font)
        df.addRow("Couleur sous-titres", self.sub_color)

        self.whisper_model = MenuCombo()
        for m in ("tiny", "base", "small", "medium"):
            self.whisper_model.addItem(m, m)
        self.whisper_model.setCurrentText("small")
        self.whisper_lang = QLineEdit("auto")
        self.whisper_gpu = QCheckBox("Utiliser GPU si disponible")
        df.addRow("Modèle Whisper", self.whisper_model)
        df.addRow("Langue Whisper", self.whisper_lang)
        df.addRow(self.whisper_gpu)

        self.music_volume = QDoubleSpinBox()
        style_spinbox(self.music_volume)
        self.music_volume.setRange(0, 1)
        self.music_volume.setSingleStep(0.05)
        self.music_volume.setValue(0.15)
        df.addRow("Volume musique défaut", self.music_volume)
        root.addWidget(defaults)

        # Updates
        updates = QGroupBox("Mises à jour en ligne")
        uf = QFormLayout(updates)
        self.update_startup = QCheckBox("Vérifier au démarrage de Clip2Tube")
        self.update_startup.setChecked(True)
        uf.addRow(self.update_startup)
        self.update_repo = QLineEdit()
        self.update_repo.setPlaceholderText("owner/repo sur GitHub")
        uf.addRow("Dépôt GitHub", self.update_repo)
        tip_up = QLabel(
            "Les versions viennent des Releases GitHub (tag vX.Y.Z + ZIP portable)."
        )
        tip_up.setObjectName("PageSubtitle")
        tip_up.setWordWrap(True)
        uf.addRow(tip_up)
        check_now = QPushButton("Vérifier les mises à jour maintenant")
        check_now.setObjectName("SecondaryButton")
        check_now.clicked.connect(self._request_update_check)
        uf.addRow(check_now)
        root.addWidget(updates)

        save = QPushButton("Enregistrer les réglages")
        save.setObjectName("BigAction")
        save.clicked.connect(self._save)
        root.addWidget(save)
        root.addStretch(1)

    def _load(self) -> None:
        c = self._config
        if not c:
            return
        self.twitch_id.setText(c.get("twitch", "client_id", default="") or "")
        self.twitch_secret.setText(c.get("twitch", "client_secret", default="") or "")
        self.google_id.setText(c.get("google", "client_id", default="") or "")
        self.google_secret.setText(c.get("google", "client_secret", default="") or "")
        self.tiktok_key.setText(c.get("tiktok", "client_key", default="") or "")
        self.tiktok_secret.setText(c.get("tiktok", "client_secret", default="") or "")
        self.ffmpeg_path.setText(c.get("ffmpeg_path", default="") or "")
        self.output_dir.setText(c.get("output_dir", default="output") or "output")
        q = c.get("video_quality", default="high") or "high"
        idx = self.quality.findText(q)
        if idx >= 0:
            self.quality.setCurrentIndex(idx)
        streamers = c.get("followed_streamers", default=[]) or []
        self.streamers_edit.setPlainText("\n".join(streamers))
        d = c.get("defaults", default={}) or {}
        self.yt_title_tpl.setText(d.get("youtube_title_template", "{titre_clip} #Shorts"))
        self.yt_desc_tpl.setPlainText(
            d.get(
                "youtube_description_template",
                "Clip de {streamer} - twitch.tv/{streamer}\n\n{hashtags}",
            )
        )
        self.tt_tpl.setText(
            d.get("tiktok_caption_template", "{titre_clip} | Clip de {streamer} {hashtags}")
        )
        self.title_font.setText(d.get("title_font", "Arial"))
        self.title_color.setText(d.get("title_color", "#FFFFFF"))
        self.sub_font.setText(d.get("subtitle_font", "Arial"))
        self.sub_color.setText(d.get("subtitle_color", "#FFFFFF"))
        self.whisper_model.setCurrentText(d.get("whisper_model", "small"))
        self.whisper_lang.setText(d.get("whisper_language", "auto"))
        self.whisper_gpu.setChecked(bool(d.get("whisper_use_gpu", False)))
        self.music_volume.setValue(float(d.get("music_volume", 0.15)))
        self.update_startup.setChecked(
            bool(c.get("updates", "check_on_startup", default=True))
        )
        self.update_repo.setText(
            c.get("updates", "github_repo", default="Arthur-Lefevre-dev/clip2tube")
            or "Arthur-Lefevre-dev/clip2tube"
        )

    def _request_update_check(self) -> None:
        self.check_updates_requested.emit()

    def _save(self) -> None:
        c = self._config
        if not c:
            return
        c.set("twitch", "client_id", self.twitch_id.text().strip())
        c.set("twitch", "client_secret", self.twitch_secret.text().strip())
        c.set("google", "client_id", self.google_id.text().strip())
        c.set("google", "client_secret", self.google_secret.text().strip())
        c.set("tiktok", "client_key", self.tiktok_key.text().strip())
        c.set("tiktok", "client_secret", self.tiktok_secret.text().strip())
        c.set("ffmpeg_path", self.ffmpeg_path.text().strip())
        c.set("output_dir", self.output_dir.text().strip() or "output")
        c.set("video_quality", self.quality.currentText())
        streamers = [
            s.strip()
            for s in self.streamers_edit.toPlainText().splitlines()
            if s.strip()
        ]
        c.set("followed_streamers", streamers)
        c.set("defaults", "youtube_title_template", self.yt_title_tpl.text())
        c.set("defaults", "youtube_description_template", self.yt_desc_tpl.toPlainText())
        c.set("defaults", "tiktok_caption_template", self.tt_tpl.text())
        c.set("defaults", "title_font", self.title_font.text())
        c.set("defaults", "title_color", self.title_color.text())
        c.set("defaults", "subtitle_font", self.sub_font.text())
        c.set("defaults", "subtitle_color", self.sub_color.text())
        c.set("defaults", "whisper_model", self.whisper_model.currentText())
        c.set("defaults", "whisper_language", self.whisper_lang.text().strip() or "auto")
        c.set("defaults", "whisper_use_gpu", self.whisper_gpu.isChecked())
        c.set("defaults", "music_volume", self.music_volume.value())
        c.set("updates", "check_on_startup", self.update_startup.isChecked())
        c.set(
            "updates",
            "github_repo",
            self.update_repo.text().strip() or "Arthur-Lefevre-dev/clip2tube",
        )
        save_config(c)
        self.log_requested.emit("Paramètres enregistrés")
        self.saved.emit()
        QMessageBox.information(
            self,
            "C’est enregistré",
            "Vos réglages sont sauvegardés.\n"
            "Vous pouvez revenir à l’accueil et chercher des clips.",
        )

    def _browse_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "ffmpeg.exe", "", "Executable (*.exe);;All (*.*)"
        )
        if path:
            self.ffmpeg_path.setText(path)

    def _detect_ffmpeg(self) -> None:
        found = find_ffmpeg(self.ffmpeg_path.text().strip())
        if found:
            self.ffmpeg_path.setText(str(found))
            QMessageBox.information(self, "FFmpeg", f"Trouvé : {found}")
        else:
            QMessageBox.warning(
                self,
                "FFmpeg",
                "Introuvable. Installez FFmpeg ou indiquez le chemin de ffmpeg.exe.",
            )

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Dossier de sortie", str(get_app_root())
        )
        if path:
            self.output_dir.setText(path)
