"""Video processing options, batch run, preview, and facecam crop picker."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QDoubleSpinBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models import Clip, Job, LayoutType
from app.models.region import FacecamRegion
from app.ui.widgets.facecam_crop import FacecamCropDialog
from app.ui.workers import PrepareCropFrameWorker, ProcessJobWorker
from app.utils.config import save_config
from app.utils.paths import get_app_root


class ProcessPage(QWidget):
    job_done = Signal(object)
    log_requested = Signal(str)
    open_queue = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pipeline = None
        self._config = None
        self._clips: list[Clip] = []
        self._worker: Optional[ProcessJobWorker] = None
        self._crop_worker: Optional[PrepareCropFrameWorker] = None
        self._queue: list[Clip] = []
        self._current_job: Optional[Job] = None
        self._music_path: Optional[Path] = None
        self._facecam_region = FacecamRegion()
        self._last_output: Optional[Path] = None
        self._build()

    def bind(self, pipeline, config) -> None:
        self._pipeline = pipeline
        self._config = config
        defaults = config.get("defaults", default={}) or {}
        layout = defaults.get("layout", LayoutType.BLUR_CENTER.value)
        idx = self.layout_combo.findData(layout)
        if idx >= 0:
            self.layout_combo.setCurrentIndex(idx)
        self.subs_check.setChecked(bool(defaults.get("subtitles_enabled", True)))
        self.title_overlay_check.setChecked(
            bool(defaults.get("burn_title_overlay", False))
        )
        self._facecam_region = FacecamRegion.from_dict(defaults.get("facecam_region"))
        # Sync size combo with saved panel ratios
        best_idx = 1
        best_dist = 99.0
        for i in range(self.facecam_size.count()):
            data = self.facecam_size.itemData(i)
            if not data:
                continue
            h_ratio, w_ratio = float(data[0]), float(data[1])
            dist = abs(h_ratio - self._facecam_region.top_ratio) + abs(
                w_ratio - self._facecam_region.width_ratio
            )
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        self.facecam_size.setCurrentIndex(best_idx)
        self._on_facecam_size_changed()
        self._refresh_facecam_label()
        self._on_layout_changed()

    def set_clips(self, clips: list[Clip]) -> None:
        self._clips = list(clips)
        self.clip_list.clear()
        for clip in clips:
            item = QListWidgetItem(
                f"{clip.title} — {clip.broadcaster_name} ({clip.duration_label})"
            )
            item.setData(Qt.ItemDataRole.UserRole, clip.id)
            self.clip_list.addItem(item)
        self.status_label.setText(f"{len(clips)} clip(s) prêts")

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        badge = QLabel("Étape 2")
        badge.setObjectName("StepBadge")
        badge.setMaximumWidth(90)
        root.addWidget(badge)

        title = QLabel("Créer ma vidéo")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        intro = QLabel(
            "Choisissez le style, (optionnel) entourez le visage du streamer, "
            "puis cliquez le grand bouton violet. "
            "Cochez « Seulement préparer » pour tester sans publier."
        )
        intro.setObjectName("PageSubtitle")
        intro.setWordWrap(True)
        root.addWidget(intro)

        body = QHBoxLayout()

        # ---- Left column in a scroll area (no QFormLayout = no overlap) ----
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_host = QWidget()
        left = QVBoxLayout(left_host)
        left.setContentsMargins(0, 0, 8, 0)
        left.setSpacing(14)

        left.addWidget(QLabel("Clips choisis"))
        self.clip_list = QListWidget()
        self.clip_list.setMaximumHeight(120)
        left.addWidget(self.clip_list)

        # Settings card — pure vertical stack
        form_box = QGroupBox("Réglages simples")
        form_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        form = QVBoxLayout(form_box)
        form.setSpacing(10)
        form.setContentsMargins(14, 18, 14, 14)

        form.addWidget(QLabel("Style de vidéo"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItem(
            "Jeu au centre + fond flou (recommandé)", LayoutType.BLUR_CENTER.value
        )
        self.layout_combo.addItem(
            "Cam en haut à gauche + clip autour (comme ton schéma)",
            LayoutType.FACECAM_SPLIT.value,
        )
        self.layout_combo.addItem(
            "Vidéo classique avec barres noires", LayoutType.LETTERBOX.value
        )
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        form.addWidget(self.layout_combo)

        self.subs_check = QCheckBox("Ajouter des sous-titres automatiques")
        self.subs_check.setChecked(True)
        form.addWidget(self.subs_check)

        self.title_overlay_check = QCheckBox("Écrire le titre sur la vidéo")
        self.title_overlay_check.setChecked(False)
        form.addWidget(self.title_overlay_check)

        self.publish_yt = QCheckBox("Envoyer sur YouTube Shorts")
        self.publish_yt.setChecked(False)
        form.addWidget(self.publish_yt)

        self.publish_tt = QCheckBox("Préparer pour TikTok (dossier export)")
        self.publish_tt.setChecked(False)
        form.addWidget(self.publish_tt)

        self.preview_only = QCheckBox("Seulement préparer la vidéo (ne pas publier)")
        self.preview_only.setChecked(True)
        form.addWidget(self.preview_only)

        form.addWidget(QLabel("Musique de fond"))
        music_row = QHBoxLayout()
        self.music_label = QLabel("Aucune")
        self.music_label.setObjectName("PageSubtitle")
        pick_music = QPushButton("Choisir une musique")
        pick_music.setObjectName("SecondaryButton")
        pick_music.clicked.connect(self._pick_music)
        clear_music = QPushButton("×")
        clear_music.setObjectName("SecondaryButton")
        clear_music.setFixedWidth(40)
        clear_music.clicked.connect(self._clear_music)
        music_row.addWidget(self.music_label, stretch=1)
        music_row.addWidget(pick_music)
        music_row.addWidget(clear_music)
        form.addLayout(music_row)

        form.addWidget(QLabel("Volume de la musique"))
        self.volume_spin = QDoubleSpinBox()
        self.volume_spin.setRange(0.0, 1.0)
        self.volume_spin.setSingleStep(0.05)
        self.volume_spin.setValue(0.15)
        form.addWidget(self.volume_spin)

        left.addWidget(form_box)

        # Facecam card
        self.facecam_box = QGroupBox("Caméra (zone rouge) + clip (zone bleue)")
        self.facecam_box.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        face = QVBoxLayout(self.facecam_box)
        face.setSpacing(10)
        face.setContentsMargins(14, 18, 14, 14)

        face.addWidget(QLabel("1. Entourez la webcam dans le clip Twitch"))
        zone_row = QHBoxLayout()
        self.facecam_label = QLabel("Pas encore choisi")
        self.facecam_label.setObjectName("PageSubtitle")
        self.facecam_label.setWordWrap(True)
        self.facecam_btn = QPushButton("Entourer le visage…")
        self.facecam_btn.setObjectName("SecondaryButton")
        self.facecam_btn.clicked.connect(self._open_facecam_picker)
        zone_row.addWidget(self.facecam_label, stretch=1)
        zone_row.addWidget(self.facecam_btn)
        face.addLayout(zone_row)

        face.addWidget(QLabel("2. Taille de la cam (haut-gauche)"))
        self.facecam_size = QComboBox()
        # (height_ratio, width_ratio) — matches red/blue sketch
        self.facecam_size.addItem("Compacte", (0.28, 0.55))
        self.facecam_size.addItem("Comme ton schéma (recommandé)", (0.33, 0.66))
        self.facecam_size.addItem("Grande", (0.40, 0.75))
        self.facecam_size.setCurrentIndex(1)
        self.facecam_size.currentIndexChanged.connect(self._on_facecam_size_changed)
        face.addWidget(self.facecam_size)

        tip = QLabel(
            "Résultat : cam en haut à gauche, le clip remplit le reste "
            "(à droite et en bas)."
        )
        tip.setObjectName("PageSubtitle")
        tip.setWordWrap(True)
        face.addWidget(tip)

        left.addWidget(self.facecam_box)

        self.run_btn = QPushButton("Créer la vidéo maintenant")
        self.run_btn.setObjectName("BigAction")
        self.run_btn.clicked.connect(self._start_batch)
        left.addWidget(self.run_btn)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        left.addWidget(self.progress)

        self.status_label = QLabel("En attente de clips…")
        self.status_label.setObjectName("PageSubtitle")
        self.status_label.setWordWrap(True)
        left.addWidget(self.status_label)
        left.addStretch(1)

        left_scroll.setWidget(left_host)
        body.addWidget(left_scroll, stretch=1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Résultat (aperçu)"))
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(270, 480)
        right.addWidget(self.video_widget, stretch=1)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)

        self.output_path_label = QLabel("Aucune vidéo créée pour le moment")
        self.output_path_label.setObjectName("PageSubtitle")
        self.output_path_label.setWordWrap(True)
        right.addWidget(self.output_path_label)

        preview_btns = QHBoxLayout()
        self.play_btn = QPushButton("▶ Lire")
        self.play_btn.setObjectName("BigAction")
        self.play_btn.clicked.connect(self._play_last)
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setObjectName("SecondaryButton")
        self.stop_btn.clicked.connect(self.player.stop)
        preview_btns.addWidget(self.play_btn)
        preview_btns.addWidget(self.stop_btn)
        right.addLayout(preview_btns)

        file_btns = QHBoxLayout()
        self.open_file_btn = QPushButton("Ouvrir la vidéo")
        self.open_file_btn.setObjectName("SecondaryButton")
        self.open_file_btn.setEnabled(False)
        self.open_file_btn.clicked.connect(self._open_video_file)
        self.open_folder_btn = QPushButton("📁 Ouvrir l’emplacement")
        self.open_folder_btn.setObjectName("SecondaryButton")
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        file_btns.addWidget(self.open_file_btn)
        file_btns.addWidget(self.open_folder_btn)
        right.addLayout(file_btns)

        body.addLayout(right, stretch=1)
        root.addLayout(body, stretch=1)

    def _on_layout_changed(self) -> None:
        is_facecam = self.layout_combo.currentData() == LayoutType.FACECAM_SPLIT.value
        self.facecam_box.setVisible(bool(is_facecam))

    def _on_facecam_size_changed(self) -> None:
        data = self.facecam_size.currentData() or (0.33, 0.66)
        self._facecam_region.top_ratio = float(data[0])
        self._facecam_region.width_ratio = float(data[1])
        self._facecam_region = self._facecam_region.clamped()

    def _refresh_facecam_label(self) -> None:
        self.facecam_label.setText(f"Zone : {self._facecam_region.label()}")

    def _open_facecam_picker(self) -> None:
        if not self._clips:
            QMessageBox.information(
                self,
                "Zone cam",
                "Ajoutez d'abord des clips (onglet Clips), puis définissez la zone.",
            )
            return
        if self._crop_worker and self._crop_worker.isRunning():
            return

        clip = self._clips[0]
        # Prefer the list selection if any
        rows = self.clip_list.selectedIndexes()
        if rows:
            clip_id = self.clip_list.item(rows[0].row()).data(Qt.ItemDataRole.UserRole)
            for c in self._clips:
                if c.id == clip_id:
                    clip = c
                    break

        ffmpeg = ""
        if self._config:
            ffmpeg = str(self._config.get("ffmpeg_path", default="") or "")

        self.facecam_btn.setEnabled(False)
        self.status_label.setText("Préparation de l'image pour le cadrage…")
        self._crop_worker = PrepareCropFrameWorker(
            clip=clip,
            dest_dir=get_app_root() / "temp",
            ffmpeg_path=ffmpeg,
        )
        self._crop_worker.progress.connect(lambda m: self.status_label.setText(m))
        self._crop_worker.finished_ok.connect(self._on_frame_ready)
        self._crop_worker.failed.connect(self._on_frame_fail)
        self._crop_worker.start()

    def _on_frame_ready(self, frame_path: str) -> None:
        self.facecam_btn.setEnabled(True)
        region = FacecamCropDialog.pick(
            Path(frame_path),
            initial=self._facecam_region,
            parent=self,
        )
        if region is None:
            self.status_label.setText("Cadrage annulé")
            return
        # Keep the chosen output panel size (red zone)
        data = self.facecam_size.currentData() or (0.33, 0.66)
        region.top_ratio = float(data[0])
        region.width_ratio = float(data[1])
        self._facecam_region = region.clamped()
        self._refresh_facecam_label()
        if self._config:
            self._config.set("defaults", "facecam_region", region.to_dict())
            save_config(self._config)
        self.status_label.setText(f"Zone cam enregistrée ({region.label()})")
        self.log_requested.emit(f"Zone facecam: {region.label()}")

    def _on_frame_fail(self, message: str) -> None:
        self.facecam_btn.setEnabled(True)
        QMessageBox.warning(self, "Zone cam", message)
        self.log_requested.emit(f"Échec cadrage cam: {message}")

    def _pick_music(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Musique de fond", "", "Audio (*.mp3 *.wav *.m4a *.aac)"
        )
        if path:
            self._music_path = Path(path)
            self.music_label.setText(self._music_path.name)

    def _clear_music(self) -> None:
        self._music_path = None
        self.music_label.setText("Aucune")

    def _start_batch(self) -> None:
        if not self._pipeline or not self._config:
            return
        if not self._clips:
            QMessageBox.information(
                self,
                "Pas encore de clips",
                "Allez d’abord à « Chercher des clips », cochez-en, "
                "puis cliquez « Créer la vidéo ».",
            )
            return
        if self._worker and self._worker.isRunning():
            return

        layout = self.layout_combo.currentData()
        if (
            layout == LayoutType.FACECAM_SPLIT.value
            and self._facecam_region.label() == FacecamRegion().label()
        ):
            tip = QMessageBox.question(
                self,
                "Zone du visage",
                "Vous n’avez pas encore entouré le visage du streamer.\n"
                "Continuer avec la zone par défaut (souvent coin haut-droit) ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if tip != QMessageBox.StandardButton.Yes:
                return

        self._config.set("defaults", "subtitles_enabled", self.subs_check.isChecked())
        self._config.set(
            "defaults", "burn_title_overlay", self.title_overlay_check.isChecked()
        )
        self._config.set("defaults", "music_volume", self.volume_spin.value())
        self._config.set("defaults", "layout", layout)
        self._config.set("defaults", "facecam_region", self._facecam_region.to_dict())
        save_config(self._config)

        self._queue = list(self._clips)
        self.run_btn.setEnabled(False)
        self._process_next()

    def _process_next(self) -> None:
        if not self._queue:
            self.run_btn.setEnabled(True)
            self.status_label.setText("Lot terminé.")
            self.log_requested.emit("Traitement du lot terminé.")
            return

        clip = self._queue.pop(0)
        layout = LayoutType(self.layout_combo.currentData())
        facecam = (
            self._facecam_region if layout == LayoutType.FACECAM_SPLIT else None
        )
        job = self._pipeline.create_job_from_clip(
            clip,
            layout=layout,
            publish_youtube=self.publish_yt.isChecked(),
            publish_tiktok=self.publish_tt.isChecked(),
            facecam_region=facecam,
        )
        self._current_job = job
        self.status_label.setText(f"Traitement: {clip.title}")
        self.progress.setValue(5)

        self._worker = ProcessJobWorker(
            self._pipeline,
            job,
            clip_url=clip.url,
            music_path=self._music_path,
            skip_publish=self.preview_only.isChecked(),
        )
        self._worker.log.connect(lambda m: self.log_requested.emit(m))
        self._worker.progress.connect(self._on_job_progress)
        self._worker.finished_ok.connect(self._on_job_ok)
        self._worker.failed.connect(self._on_job_fail)
        self._worker.start()

    def _on_job_progress(self, job: Job) -> None:
        self.progress.setValue(int(job.progress))
        self.status_label.setText(f"{job.status.value} — {job.clip_title}")

    def _on_job_ok(self, job: Job) -> None:
        self.job_done.emit(job)
        if job.output_path and Path(job.output_path).exists():
            self._set_last_output(Path(job.output_path))
            self.status_label.setText(f"Vidéo prête : {Path(job.output_path).name}")
            # Auto-play preview for the latest render
            self.player.play()
        self.progress.setValue(100)
        self._process_next()

    def _on_job_fail(self, message: str) -> None:
        self.log_requested.emit(f"Échec: {message}")
        QMessageBox.warning(self, "Traitement", message)
        self._process_next()

    def _set_last_output(self, path: Path) -> None:
        self._last_output = path
        self.output_path_label.setText(f"Fichier : {path}")
        self.open_file_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(True)
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(path.resolve())))

    def _play_last(self) -> None:
        if not self._last_output or not self._last_output.exists():
            QMessageBox.information(
                self,
                "Aucune vidéo",
                "Créez d’abord une vidéo, puis vous pourrez la lire ici.",
            )
            return
        # Reload source in case the player was cleared
        self.player.setSource(QUrl.fromLocalFile(str(self._last_output.resolve())))
        self.player.play()

    def _open_video_file(self) -> None:
        if not self._last_output or not self._last_output.exists():
            QMessageBox.information(self, "Fichier", "Aucune vidéo à ouvrir.")
            return
        try:
            os.startfile(str(self._last_output.resolve()))  # type: ignore[attr-defined]
        except Exception as exc:
            QMessageBox.warning(self, "Ouverture", f"Impossible d’ouvrir la vidéo:\n{exc}")

    def _open_output_folder(self) -> None:
        if not self._last_output or not self._last_output.exists():
            QMessageBox.information(self, "Dossier", "Aucune vidéo — pas de dossier à ouvrir.")
            return
        path = self._last_output.resolve()
        try:
            # Highlight the file in Explorer
            subprocess.run(
                ["explorer", "/select,", str(path)],
                check=False,
            )
        except Exception as exc:
            # Fallback: open the parent folder
            try:
                os.startfile(str(path.parent))  # type: ignore[attr-defined]
            except Exception:
                QMessageBox.warning(
                    self, "Dossier", f"Impossible d’ouvrir l’emplacement:\n{exc}"
                )
