"""Video processing options, batch run, preview, and facecam crop picker."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QUrl, QRectF, QSizeF
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models import Clip, Job, LayoutType, layout_needs_facecam
from app.models.region import FacecamRegion
from app.ui.widgets.facecam_crop import FacecamCropDialog
from app.ui.widgets.layout_picker import LayoutPicker
from app.ui.widgets.menu_combo import MenuCombo
from app.ui.workers import PrepareCropFrameWorker, ProcessJobWorker
from app.utils.config import save_config
from app.utils.paths import get_app_root


class ProcessPage(QWidget):
    job_done = Signal(object)
    log_requested = Signal(str)
    open_queue = Signal()
    go_to = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pipeline = None
        self._config = None
        self._clips: list[Clip] = []
        self._worker: Optional[ProcessJobWorker] = None
        self._crop_worker: Optional[PrepareCropFrameWorker] = None
        self._queue: list[Clip] = []
        self._current_job: Optional[Job] = None
        self._pending_clip: Optional[Clip] = None
        self._facecam_region = FacecamRegion()
        self._last_output: Optional[Path] = None
        self._batch_outputs: list[Path] = []
        self._preview_index: int = -1
        self._build()

    def bind(self, pipeline, config) -> None:
        self._pipeline = pipeline
        self._config = config
        defaults = config.get("defaults", default={}) or {}
        layout = defaults.get("layout", LayoutType.BLUR_CENTER.value)
        self.layout_picker.set_layout(str(layout))
        self.subs_check.setChecked(bool(defaults.get("subtitles_enabled", True)))
        self.title_overlay_check.setChecked(
            bool(defaults.get("burn_title_overlay", False))
        )
        self._facecam_region = FacecamRegion.from_dict(defaults.get("facecam_region"))
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
                f"{clip.title}\n{clip.broadcaster_name} · {clip.duration_label}"
            )
            item.setData(Qt.ItemDataRole.UserRole, clip.id)
            self.clip_list.addItem(item)
        n = len(clips)
        self.clip_count.setText(f"{n}")
        self.empty_clips.setVisible(n == 0)
        self.clip_list.setVisible(n > 0)
        self.find_clips_btn.setVisible(n == 0)
        if n:
            self.status_label.setText(f"{n} clip(s) prêts à monter")
        else:
            self.status_label.setText("Aucun clip — allez d’abord en chercher.")

    def _card(self, title: str, hint: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("ProcessCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        head = QHBoxLayout()
        t = QLabel(title)
        t.setObjectName("ProcessCardTitle")
        head.addWidget(t)
        head.addStretch(1)
        lay.addLayout(head)
        if hint:
            h = QLabel(hint)
            h.setObjectName("ProcessHint")
            h.setWordWrap(True)
            lay.addWidget(h)
        return card, lay

    def _build(self) -> None:
        # Sticky preview on the right (viewport height); only the left column scrolls.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 20, 20)
        outer.setSpacing(14)

        # —— Header (stays visible, does not scroll away with left forms) ——
        badge = QLabel("Étape 2")
        badge.setObjectName("StepBadge")
        badge.setMaximumWidth(90)
        outer.addWidget(badge)

        title = QLabel("Créer ma vidéo")
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        intro = QLabel(
            "Choisissez un style, lancez la création, puis regardez l’aperçu à droite. "
            "Par défaut on prépare seulement la vidéo (sans publier)."
        )
        intro.setObjectName("PageSubtitle")
        intro.setWordWrap(True)
        outer.addWidget(intro)

        body = QHBoxLayout()
        body.setSpacing(16)

        # ================= LEFT (scrollable) =================
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_host = QWidget()
        left = QVBoxLayout(left_host)
        left.setContentsMargins(0, 0, 8, 0)
        left.setSpacing(12)

        # Clips
        clips_card, clips_lay = self._card(
            "Clips à monter",
            "Ceux que vous avez cochés à l’étape 1.",
        )
        count_row = clips_lay.itemAt(0).layout()
        self.clip_count = QLabel("0")
        self.clip_count.setObjectName("ClipCountBadge")
        count_row.addWidget(self.clip_count)

        self.empty_clips = QLabel(
            "Aucun clip pour l’instant.\nCherchez-en d’abord, puis revenez ici."
        )
        self.empty_clips.setObjectName("EmptyHint")
        self.empty_clips.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_clips.setWordWrap(True)
        clips_lay.addWidget(self.empty_clips)

        self.find_clips_btn = QPushButton("Aller chercher des clips")
        self.find_clips_btn.setObjectName("SecondaryButton")
        self.find_clips_btn.clicked.connect(lambda: self.go_to.emit("clips"))
        clips_lay.addWidget(self.find_clips_btn)

        self.clip_list = QListWidget()
        self.clip_list.setMinimumHeight(100)
        self.clip_list.setMaximumHeight(150)
        self.clip_list.setVisible(False)
        clips_lay.addWidget(self.clip_list)
        left.addWidget(clips_card)

        # Style — illustrated choice buttons
        style_card, style_lay = self._card(
            "1 · Style de la vidéo",
            "Cliquez sur le format qui vous plaît.",
        )
        self.layout_picker = LayoutPicker()
        self.layout_picker.layout_changed.connect(self._on_layout_changed)
        style_lay.addWidget(self.layout_picker)
        left.addWidget(style_card)

        # Facecam (shown only for facecam layout)
        self.facecam_box, face = self._card(
            "Zone webcam",
            "Entourez le visage dans le clip, puis choisissez la taille de la pastille.",
        )
        zone_row = QHBoxLayout()
        self.facecam_label = QLabel("Pas encore choisi")
        self.facecam_label.setObjectName("ProcessHint")
        self.facecam_label.setWordWrap(True)
        self.facecam_btn = QPushButton("Entourer le visage…")
        self.facecam_btn.setObjectName("SecondaryButton")
        self.facecam_btn.clicked.connect(self._open_facecam_picker)
        zone_row.addWidget(self.facecam_label, stretch=1)
        zone_row.addWidget(self.facecam_btn)
        face.addLayout(zone_row)

        self.facecam_size_label = QLabel("Taille de la caméra (style L)")
        face.addWidget(self.facecam_size_label)
        self.facecam_size = MenuCombo()
        self.facecam_size.addItem("Compacte", (0.28, 0.55))
        self.facecam_size.addItem("Équilibrée (recommandé)", (0.33, 0.66))
        self.facecam_size.addItem("Grande", (0.40, 0.75))
        self.facecam_size.setCurrentIndex(1)
        self.facecam_size.currentIndexChanged.connect(
            lambda _i: self._on_facecam_size_changed()
        )
        face.addWidget(self.facecam_size)

        self.facecam_each_clip = QCheckBox(
            "Recadrer la cam à chaque clip (si elle bouge)"
        )
        self.facecam_each_clip.setChecked(True)
        self.facecam_each_clip.setToolTip(
            "Avant chaque rendu, vous entourez le visage sur ce clip-là."
        )
        face.addWidget(self.facecam_each_clip)
        left.addWidget(self.facecam_box)

        # Options
        opt_card, opt_lay = self._card("2 · Options")
        self.subs_check = QCheckBox("Sous-titres automatiques")
        self.subs_check.setChecked(True)
        opt_lay.addWidget(self.subs_check)

        self.title_overlay_check = QCheckBox("Afficher le titre sur la vidéo")
        self.title_overlay_check.setChecked(False)
        opt_lay.addWidget(self.title_overlay_check)
        left.addWidget(opt_card)

        # Destination
        dest_card, dest_lay = self._card(
            "3 · Ensuite ?",
            "Le plus simple : préparer d’abord, publier plus tard depuis « Mes vidéos ».",
        )
        self.preview_only = QCheckBox("Seulement préparer (recommandé)")
        self.preview_only.setChecked(True)
        dest_lay.addWidget(self.preview_only)
        self.publish_yt = QCheckBox("Publier aussi sur YouTube Shorts")
        self.publish_yt.setChecked(False)
        dest_lay.addWidget(self.publish_yt)
        self.publish_tt = QCheckBox("Exporter aussi pour TikTok")
        self.publish_tt.setChecked(False)
        dest_lay.addWidget(self.publish_tt)
        left.addWidget(dest_card)

        # CTA
        self.run_btn = QPushButton("Créer la vidéo maintenant")
        self.run_btn.setObjectName("BigAction")
        self.run_btn.clicked.connect(self._start_batch)
        left.addWidget(self.run_btn)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        left.addWidget(self.progress)

        self.status_label = QLabel("En attente de clips…")
        self.status_label.setObjectName("PageSubtitle")
        self.status_label.setWordWrap(True)
        left.addWidget(self.status_label)
        left.addStretch(1)

        left_scroll.setWidget(left_host)
        body.addWidget(left_scroll, stretch=1)

        # ================= RIGHT: sticky preview (viewport-sized) =================
        self._preview_shell = QFrame()
        self._preview_shell.setObjectName("PreviewShell")
        self._preview_shell.setFixedWidth(320)
        self._preview_shell.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        right = QVBoxLayout(self._preview_shell)
        right.setContentsMargins(12, 12, 12, 12)
        right.setSpacing(12)

        prev_title = QLabel("Aperçu")
        prev_title.setObjectName("ProcessCardTitle")
        right.addWidget(prev_title, 0)

        # Middle: phone only (buttons live in a separate bottom block → no overlap)
        self._phone_area = QWidget()
        self._phone_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        phone_area_lay = QVBoxLayout(self._phone_area)
        phone_area_lay.setContentsMargins(0, 0, 0, 0)
        phone_area_lay.setSpacing(0)
        phone_area_lay.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )

        self._phone = QFrame()
        self._phone.setObjectName("PreviewPhone")
        self._phone.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        phone_lay = QVBoxLayout(self._phone)
        phone_lay.setContentsMargins(0, 0, 0, 0)
        phone_lay.setSpacing(0)

        self.preview_empty = QLabel("L’aperçu 9:16\napparaîtra ici.")
        self.preview_empty.setObjectName("PreviewEmpty")
        self.preview_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_empty.setWordWrap(True)
        phone_lay.addWidget(self.preview_empty)

        # Graphics video fills the phone exactly (no letterbox bars in the UI)
        self._video_scene = QGraphicsScene(self)
        self._video_item = QGraphicsVideoItem()
        self._video_scene.addItem(self._video_item)
        self.video_view = QGraphicsView(self._video_scene)
        self.video_view.setObjectName("PreviewVideoView")
        self.video_view.setFrameShape(QFrame.Shape.NoFrame)
        self.video_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.video_view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.video_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_view.setStyleSheet("background: #000; border: none;")
        self.video_view.setVisible(False)
        phone_lay.addWidget(self.video_view, stretch=1)
        phone_area_lay.addWidget(self._phone, 0, Qt.AlignmentFlag.AlignHCenter)
        right.addWidget(self._phone_area, 1)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self._video_item)
        self._video_item.nativeSizeChanged.connect(self._fit_video_item)

        # Bottom controls — never share space with the phone
        controls = QWidget()
        controls.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        controls_lay = QVBoxLayout(controls)
        controls_lay.setContentsMargins(0, 4, 0, 0)
        controls_lay.setSpacing(10)

        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.prev_preview_btn = QPushButton("◀ Préc.")
        self.prev_preview_btn.setObjectName("SecondaryButton")
        self.prev_preview_btn.setEnabled(False)
        self.prev_preview_btn.setToolTip("Clip précédent du lot")
        self.prev_preview_btn.clicked.connect(lambda: self._nav_preview(-1))
        self.preview_index_label = QLabel("0 / 0")
        self.preview_index_label.setObjectName("ProcessHint")
        self.preview_index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_preview_btn = QPushButton("Suiv. ▶")
        self.next_preview_btn.setObjectName("SecondaryButton")
        self.next_preview_btn.setEnabled(False)
        self.next_preview_btn.setToolTip("Clip suivant du lot")
        self.next_preview_btn.clicked.connect(lambda: self._nav_preview(1))
        nav.addWidget(self.prev_preview_btn)
        nav.addWidget(self.preview_index_label, stretch=1)
        nav.addWidget(self.next_preview_btn)
        controls_lay.addLayout(nav)

        self.output_path_label = QLabel("Aucune vidéo créée")
        self.output_path_label.setObjectName("ProcessHint")
        self.output_path_label.setWordWrap(True)
        controls_lay.addWidget(self.output_path_label)

        preview_btns = QHBoxLayout()
        preview_btns.setSpacing(8)
        self.play_btn = QPushButton("▶  Lire")
        self.play_btn.setObjectName("BigAction")
        self.play_btn.clicked.connect(self._play_last)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("SecondaryButton")
        self.stop_btn.clicked.connect(self.player.stop)
        preview_btns.addWidget(self.play_btn, stretch=2)
        preview_btns.addWidget(self.stop_btn, stretch=1)
        controls_lay.addLayout(preview_btns)

        file_btns = QHBoxLayout()
        file_btns.setSpacing(8)
        self.open_file_btn = QPushButton("Ouvrir")
        self.open_file_btn.setObjectName("SecondaryButton")
        self.open_file_btn.setEnabled(False)
        self.open_file_btn.clicked.connect(self._open_video_file)
        self.open_folder_btn = QPushButton("Dossier")
        self.open_folder_btn.setObjectName("SecondaryButton")
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        file_btns.addWidget(self.open_file_btn)
        file_btns.addWidget(self.open_folder_btn)
        controls_lay.addLayout(file_btns)

        right.addWidget(controls, 0)

        body.addWidget(self._preview_shell)
        outer.addLayout(body, stretch=1)
        self._fit_preview_phone()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_preview_phone()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._fit_preview_phone()

    def _fit_preview_phone(self) -> None:
        """Size the 9:16 phone to the middle area only (above the buttons)."""
        if not hasattr(self, "_phone_area") or not hasattr(self, "_phone"):
            return
        area = self._phone_area
        avail_h = max(180, area.height() - 4)
        avail_w = max(120, min(296, area.width() - 4))
        if avail_h < 40 or avail_w < 40:
            return
        h_from_w = int(avail_w * 16 / 9)
        w_from_h = int(avail_h * 9 / 16)
        if h_from_w <= avail_h:
            w, h = avail_w, h_from_w
        else:
            w, h = w_from_h, avail_h
        w = max(120, min(w, avail_w))
        h = max(180, min(h, avail_h))
        self._phone.setFixedSize(w, h)
        self._fit_video_item()

    def _fit_video_item(self, *_args) -> None:
        """Stretch the video item to cover the phone view (crop overflow if needed)."""
        if not hasattr(self, "video_view") or not hasattr(self, "_video_item"):
            return
        vw = max(1, self.video_view.viewport().width())
        vh = max(1, self.video_view.viewport().height())
        self.video_view.setSceneRect(QRectF(0, 0, vw, vh))
        native = self._video_item.nativeSize()
        if native.width() <= 0 or native.height() <= 0:
            self._video_item.setSize(QSizeF(vw, vh))
            self._video_item.setPos(0, 0)
            return
        # Cover-fit 9:16 viewport (same idea as CSS object-fit: cover)
        scale = max(vw / native.width(), vh / native.height())
        tw = native.width() * scale
        th = native.height() * scale
        self._video_item.setSize(QSizeF(tw, th))
        self._video_item.setPos((vw - tw) / 2, (vh - th) / 2)

    def _on_layout_changed(self, *_args) -> None:
        layout = self.layout_picker.currentData()
        needs = layout_needs_facecam(layout)
        self.facecam_box.setVisible(needs)
        # Panel size only applies to the L / PIP style
        is_pip = layout == LayoutType.FACECAM_SPLIT.value
        self.facecam_size.setVisible(is_pip)
        self.facecam_size_label.setVisible(is_pip)

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
                "Ajoutez d’abord des clips (étape 1), puis définissez la zone.",
            )
            return
        if self._crop_worker and self._crop_worker.isRunning():
            return

        clip = self._clips[0]
        rows = self.clip_list.selectedIndexes()
        if rows:
            clip_id = self.clip_list.item(rows[0].row()).data(Qt.ItemDataRole.UserRole)
            for c in self._clips:
                if c.id == clip_id:
                    clip = c
                    break

        self.status_label.setText("Préparation de l’image pour le cadrage…")
        self._prepare_facecam_for_clip(clip, for_batch=False)

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

    def _start_batch(self) -> None:
        if not self._pipeline or not self._config:
            return
        if not self._clips:
            reply = QMessageBox.question(
                self,
                "Pas encore de clips",
                "Aucun clip à monter.\nVoulez-vous aller en chercher ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.go_to.emit("clips")
            return
        if self._worker and self._worker.isRunning():
            return

        layout = self.layout_picker.currentData()
        if (
            layout_needs_facecam(layout)
            and self._facecam_region.label() == FacecamRegion().label()
        ):
            tip = QMessageBox.question(
                self,
                "Zone du visage",
                "Vous n’avez pas encore entouré le visage du streamer.\n"
                "Continuer avec la zone par défaut ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if tip != QMessageBox.StandardButton.Yes:
                return

        self._config.set("defaults", "subtitles_enabled", self.subs_check.isChecked())
        self._config.set(
            "defaults", "burn_title_overlay", self.title_overlay_check.isChecked()
        )
        self._config.set("defaults", "layout", layout)
        self._config.set("defaults", "facecam_region", self._facecam_region.to_dict())
        save_config(self._config)

        self._queue = list(self._clips)
        self._batch_outputs = []
        self._preview_index = -1
        self._update_preview_nav()
        self.run_btn.setEnabled(False)
        self._process_next()

    def _process_next(self) -> None:
        if not self._queue:
            self._pending_clip = None
            self.run_btn.setEnabled(True)
            n = len(self._batch_outputs)
            self.status_label.setText(
                f"Lot terminé — {n} vidéo(s). Naviguez dans l’aperçu ◀ ▶"
                if n
                else "Terminé."
            )
            self.log_requested.emit("Traitement du lot terminé.")
            return

        clip = self._queue.pop(0)
        layout = LayoutType(self.layout_picker.currentData())
        needs_cam = layout_needs_facecam(layout)
        recrop = needs_cam and self.facecam_each_clip.isChecked()

        if recrop:
            self._pending_clip = clip
            self.status_label.setText(
                f"Recadrage cam pour : {clip.title[:60]}"
            )
            self._prepare_facecam_for_clip(clip, for_batch=True)
            return

        self._start_job_for_clip(clip, self._facecam_region if needs_cam else None)

    def _prepare_facecam_for_clip(self, clip: Clip, *, for_batch: bool) -> None:
        if self._crop_worker and self._crop_worker.isRunning():
            return
        ffmpeg = ""
        if self._config:
            ffmpeg = str(self._config.get("ffmpeg_path", default="") or "")
        self.facecam_btn.setEnabled(False)
        self._crop_worker = PrepareCropFrameWorker(
            clip=clip,
            dest_dir=get_app_root() / "temp",
            ffmpeg_path=ffmpeg,
        )
        self._crop_worker.progress.connect(lambda m: self.status_label.setText(m))
        if for_batch:
            self._crop_worker.finished_ok.connect(self._on_batch_frame_ready)
            self._crop_worker.failed.connect(self._on_batch_frame_fail)
        else:
            self._crop_worker.finished_ok.connect(self._on_frame_ready)
            self._crop_worker.failed.connect(self._on_frame_fail)
        self._crop_worker.start()

    def _on_batch_frame_ready(self, frame_path: str) -> None:
        self.facecam_btn.setEnabled(True)
        clip = self._pending_clip
        if clip is None:
            self._process_next()
            return
        region = FacecamCropDialog.pick(
            Path(frame_path),
            initial=self._facecam_region,
            parent=self,
            title=f"Zone cam — {clip.title[:50]}",
        )
        if region is None:
            skip = QMessageBox.question(
                self,
                "Cadrage annulé",
                "Passer ce clip et continuer le lot ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if skip == QMessageBox.StandardButton.Yes:
                self._pending_clip = None
                self._process_next()
            else:
                self._queue.insert(0, clip)
                self._pending_clip = None
                self.run_btn.setEnabled(True)
                self.status_label.setText("Lot en pause")
            return

        data = self.facecam_size.currentData() or (0.33, 0.66)
        region.top_ratio = float(data[0])
        region.width_ratio = float(data[1])
        self._facecam_region = region.clamped()
        self._refresh_facecam_label()
        if self._config:
            self._config.set("defaults", "facecam_region", region.to_dict())
            save_config(self._config)
        self._pending_clip = None
        self._start_job_for_clip(clip, self._facecam_region)

    def _on_batch_frame_fail(self, message: str) -> None:
        self.facecam_btn.setEnabled(True)
        clip = self._pending_clip
        self._pending_clip = None
        self.log_requested.emit(f"Échec cadrage cam: {message}")
        use_default = QMessageBox.question(
            self,
            "Zone cam",
            f"Impossible de préparer le cadrage.\n{message}\n\n"
            "Utiliser la dernière zone connue pour ce clip ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if clip and use_default == QMessageBox.StandardButton.Yes:
            self._start_job_for_clip(clip, self._facecam_region)
        else:
            self._process_next()

    def _start_job_for_clip(
        self, clip: Clip, facecam: FacecamRegion | None
    ) -> None:
        if not self._pipeline:
            return
        layout = LayoutType(self.layout_picker.currentData())
        job = self._pipeline.create_job_from_clip(
            clip,
            layout=layout,
            publish_youtube=self.publish_yt.isChecked()
            and not self.preview_only.isChecked(),
            publish_tiktok=self.publish_tt.isChecked()
            and not self.preview_only.isChecked(),
            facecam_region=facecam,
        )
        self._current_job = job
        left = len(self._queue)
        self.status_label.setText(
            f"Création : {clip.title}  ·  {left} restant(s)"
        )
        self.progress.setValue(5)

        self._worker = ProcessJobWorker(
            self._pipeline,
            job,
            clip_url=clip.url,
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
            path = Path(job.output_path)
            self._batch_outputs.append(path)
            self._preview_index = len(self._batch_outputs) - 1
            self._show_preview_at(self._preview_index, autoplay=True)
            self.status_label.setText(f"Vidéo prête : {path.name}")
        self.progress.setValue(100)
        self._process_next()

    def _on_job_fail(self, message: str) -> None:
        self.log_requested.emit(f"Échec: {message}")
        QMessageBox.warning(self, "Création", message)
        self._process_next()

    def _update_preview_nav(self) -> None:
        n = len(self._batch_outputs)
        idx = self._preview_index
        if n == 0:
            self.preview_index_label.setText("0 / 0")
            self.prev_preview_btn.setEnabled(False)
            self.next_preview_btn.setEnabled(False)
            return
        self.preview_index_label.setText(f"{idx + 1} / {n}")
        self.prev_preview_btn.setEnabled(idx > 0)
        self.next_preview_btn.setEnabled(idx < n - 1)

    def _nav_preview(self, delta: int) -> None:
        if not self._batch_outputs:
            return
        new_idx = self._preview_index + delta
        if new_idx < 0 or new_idx >= len(self._batch_outputs):
            return
        self._show_preview_at(new_idx, autoplay=True)

    def _show_preview_at(self, index: int, *, autoplay: bool = False) -> None:
        if index < 0 or index >= len(self._batch_outputs):
            return
        path = self._batch_outputs[index]
        self._preview_index = index
        self._last_output = path
        name = path.name
        if len(name) > 36:
            name = name[:16] + "…" + name[-16:]
        self.output_path_label.setText(name)
        self.output_path_label.setToolTip(str(path))
        self.open_file_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(True)
        self.preview_empty.setVisible(False)
        self.video_view.setVisible(True)
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self._update_preview_nav()
        self._fit_preview_phone()
        if autoplay:
            self.player.play()

    def _set_last_output(self, path: Path) -> None:
        if path not in self._batch_outputs:
            self._batch_outputs.append(path)
        self._show_preview_at(len(self._batch_outputs) - 1, autoplay=False)

    def _play_last(self) -> None:
        if self._preview_index >= 0 and self._batch_outputs:
            self._show_preview_at(self._preview_index, autoplay=True)
            return
        if not self._last_output or not self._last_output.exists():
            QMessageBox.information(
                self,
                "Aucune vidéo",
                "Créez d’abord une vidéo, puis vous pourrez la lire ici.",
            )
            return
        self._set_last_output(self._last_output)
        self.player.play()

    def _open_video_file(self) -> None:
        if not self._last_output or not self._last_output.exists():
            QMessageBox.information(self, "Fichier", "Aucune vidéo à ouvrir.")
            return
        try:
            os.startfile(str(self._last_output.resolve()))  # type: ignore[attr-defined]
        except Exception as exc:
            QMessageBox.warning(
                self, "Ouverture", f"Impossible d’ouvrir la vidéo:\n{exc}"
            )

    def _open_output_folder(self) -> None:
        if not self._last_output or not self._last_output.exists():
            QMessageBox.information(
                self, "Dossier", "Aucune vidéo — pas de dossier à ouvrir."
            )
            return
        path = self._last_output.resolve()
        try:
            subprocess.run(
                ["explorer", "/select,", str(path)],
                check=False,
            )
        except Exception as exc:
            try:
                os.startfile(str(path.parent))  # type: ignore[attr-defined]
            except Exception:
                QMessageBox.warning(
                    self, "Dossier", f"Impossible d’ouvrir l’emplacement:\n{exc}"
                )
