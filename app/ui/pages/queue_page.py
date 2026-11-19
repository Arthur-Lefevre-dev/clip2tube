"""Mes vidéos — rendered jobs, publish / schedule / open."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize, QThread
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models import Job, JobStatus
from app.ui.widgets.video_job_row import VideoJobRow
from app.ui.workers import PublishJobWorker
from app.utils.ffmpeg import find_ffmpeg, run_ffmpeg
from app.utils.paths import get_app_root


class _ThumbWorker(QThread):
    """Extract a JPEG frame from a finished vertical video."""

    finished_ok = Signal(str, str)  # job_id, frame_path
    failed = Signal(str, str)

    def __init__(self, job_id: str, video: Path, ffmpeg_path: str = "", parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.video = video
        self.ffmpeg_path = ffmpeg_path

    def run(self) -> None:
        try:
            out = get_app_root() / "temp" / f"jobthumb_{self.job_id}.jpg"
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists() and out.stat().st_size > 0:
                self.finished_ok.emit(self.job_id, str(out))
                return
            binary = find_ffmpeg(self.ffmpeg_path)
            if not binary:
                self.failed.emit(self.job_id, "ffmpeg missing")
                return
            result = run_ffmpeg(
                [
                    "-ss",
                    "0.8",
                    "-i",
                    str(self.video),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "4",
                    "-y",
                    str(out),
                ],
                ffmpeg_path=binary,
                timeout=60,
            )
            if result.returncode != 0 or not out.exists():
                self.failed.emit(self.job_id, "thumb failed")
                return
            self.finished_ok.emit(self.job_id, str(out))
        except Exception as exc:
            self.failed.emit(self.job_id, str(exc))


class QueuePage(QWidget):
    log_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._db = None
        self._pipeline = None
        self._worker: Optional[PublishJobWorker] = None
        self._rows: dict[str, VideoJobRow] = {}
        self._jobs: dict[str, Job] = {}
        self._thumb_workers: list[_ThumbWorker] = []
        self._build()

    def bind(self, database, pipeline) -> None:
        self._db = database
        self._pipeline = pipeline
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(14)

        badge = QLabel("Étape 3")
        badge.setObjectName("StepBadge")
        badge.setMaximumWidth(90)
        root.addWidget(badge)

        title = QLabel("Mes vidéos")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        sub = QLabel(
            "Gérez vos montages : modifier les infos, supprimer, ouvrir, "
            "planifier ou publier sur YouTube."
        )
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(sub)

        tools = QHBoxLayout()
        tools.setSpacing(8)
        refresh = QPushButton("Rafraîchir")
        refresh.setObjectName("SecondaryButton")
        refresh.clicked.connect(self.refresh)
        tools.addWidget(refresh)
        self.clear_btn = QPushButton("Tout vider")
        self.clear_btn.setObjectName("SecondaryButton")
        self.clear_btn.clicked.connect(self._clear_all)
        tools.addWidget(self.clear_btn)
        tools.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("PageSubtitle")
        tools.addWidget(self.count_label)
        root.addLayout(tools)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("VideoJobList")
        self.list_widget.setSpacing(0)
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list_widget.currentItemChanged.connect(self._on_selection)
        self.list_widget.itemDoubleClicked.connect(lambda _i: self._edit_selected())
        root.addWidget(self.list_widget, stretch=1)

        self.empty = QLabel(
            "Aucune vidéo pour l’instant.\n"
            "Créez-en une depuis « Traitement », elle apparaîtra ici."
        )
        self.empty.setObjectName("EmptyHint")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        root.addWidget(self.empty)

        crud = QHBoxLayout()
        crud.setSpacing(8)
        self.edit_btn = QPushButton("Modifier")
        self.edit_btn.setObjectName("SecondaryButton")
        self.edit_btn.clicked.connect(self._edit_selected)
        self.delete_btn = QPushButton("Supprimer")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self._delete_selected)
        crud.addWidget(self.edit_btn)
        crud.addWidget(self.delete_btn)
        crud.addStretch(1)
        root.addLayout(crud)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.open_btn = QPushButton("Ouvrir")
        self.open_btn.setObjectName("SecondaryButton")
        self.open_btn.clicked.connect(self._open_selected_video)
        self.folder_btn = QPushButton("Dossier")
        self.folder_btn.setObjectName("SecondaryButton")
        self.folder_btn.clicked.connect(self._open_selected_folder)
        self.retry_btn = QPushButton("Réessayer")
        self.retry_btn.setObjectName("SecondaryButton")
        self.retry_btn.clicked.connect(self._retry_selected)
        self.schedule_btn = QPushButton("Planifier…")
        self.schedule_btn.setObjectName("SecondaryButton")
        self.schedule_btn.clicked.connect(self._schedule_selected)
        self.publish_btn = QPushButton("Publier maintenant")
        self.publish_btn.setObjectName("BigAction")
        self.publish_btn.clicked.connect(self._publish_selected)
        for btn in (
            self.open_btn,
            self.folder_btn,
            self.retry_btn,
            self.schedule_btn,
            self.publish_btn,
        ):
            actions.addWidget(btn)
        actions.addStretch(1)
        root.addLayout(actions)
        self._set_actions_enabled(False)

    def refresh(self) -> None:
        if not self._db:
            return
        jobs = self._db.list_jobs(200)
        self._rows.clear()
        self._jobs.clear()
        self.list_widget.clear()
        for job in jobs:
            self._jobs[job.id] = job
            item = QListWidgetItem(self.list_widget)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setData(Qt.ItemDataRole.UserRole, job.id)
            row = VideoJobRow(job)
            item.setSizeHint(row.sizeHint().expandedTo(QSize(0, 112)))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)
            self._rows[job.id] = row
            row.clicked.connect(
                lambda it=item: self.list_widget.setCurrentItem(it)
            )
            if job.output_path and Path(job.output_path).exists():
                self._queue_thumb(job)

        n = len(jobs)
        self.count_label.setText(f"{n} vidéo{'s' if n != 1 else ''}")
        self.empty.setVisible(n == 0)
        self.list_widget.setVisible(n > 0)
        self._on_selection(self.list_widget.currentItem(), None)

    def _queue_thumb(self, job: Job) -> None:
        ffmpeg = ""
        if self._pipeline and getattr(self._pipeline, "editor", None):
            ffmpeg = str(getattr(self._pipeline.editor, "ffmpeg_path", "") or "")
        worker = _ThumbWorker(job.id, Path(job.output_path), ffmpeg_path=ffmpeg)
        worker.finished_ok.connect(self._on_thumb_ready)
        self._thumb_workers.append(worker)
        worker.start()

    def _on_thumb_ready(self, job_id: str, frame_path: str) -> None:
        row = self._rows.get(job_id)
        if not row:
            return
        pix = QPixmap(frame_path)
        if not pix.isNull():
            row.set_thumbnail(pix)

    def _on_selection(
        self, current: QListWidgetItem | None, _prev: QListWidgetItem | None
    ) -> None:
        selected = (
            str(current.data(Qt.ItemDataRole.UserRole) or "") if current else ""
        )
        for job_id, row in self._rows.items():
            row.set_selected(job_id == selected)
        job = self._jobs.get(selected) if selected else None
        has_file = bool(
            job and job.output_path and Path(job.output_path).exists()
        )
        self._set_actions_enabled(bool(job), has_file=has_file)

    def _set_actions_enabled(self, has_job: bool, has_file: bool = False) -> None:
        self.edit_btn.setEnabled(has_job)
        self.delete_btn.setEnabled(has_job)
        self.open_btn.setEnabled(has_file)
        self.folder_btn.setEnabled(has_file)
        self.retry_btn.setEnabled(has_job)
        self.schedule_btn.setEnabled(has_file)
        self.publish_btn.setEnabled(has_file)
        self.clear_btn.setEnabled(bool(self._jobs))

    def _selected_job(self) -> Optional[Job]:
        item = self.list_widget.currentItem()
        if not item or not self._db:
            return None
        job_id = item.data(Qt.ItemDataRole.UserRole)
        if not job_id:
            return None
        return self._db.get_job(str(job_id))

    def _edit_selected(self) -> None:
        job = self._selected_job()
        if not job or not self._db:
            QMessageBox.information(
                self, "Modifier", "Sélectionnez d’abord une vidéo."
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Modifier la vidéo")
        dlg.resize(480, 420)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        title_edit = QLineEdit(job.clip_title)
        streamer_edit = QLineEdit(job.streamer)
        yt_title = QLineEdit(job.youtube_title or job.clip_title)
        yt_desc = QTextEdit()
        yt_desc.setPlainText(job.youtube_description or "")
        yt_desc.setMinimumHeight(100)
        tt_cap = QLineEdit(job.tiktok_caption or "")
        form.addRow("Titre", title_edit)
        form.addRow("Streamer", streamer_edit)
        form.addRow("Titre YouTube", yt_title)
        form.addRow("Description YT", yt_desc)
        form.addRow("Légende TikTok", tt_cap)
        lay.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_title = title_edit.text().strip()
        if not new_title:
            QMessageBox.warning(self, "Modifier", "Le titre ne peut pas être vide.")
            return
        job.clip_title = new_title
        job.streamer = streamer_edit.text().strip() or job.streamer
        job.youtube_title = yt_title.text().strip()
        job.youtube_description = yt_desc.toPlainText().strip()
        job.tiktok_caption = tt_cap.text().strip()
        self._db.upsert_job(job)
        self.refresh()
        self.log_requested.emit(f"Vidéo modifiée : {job.clip_title}")

    def _delete_selected(self) -> None:
        job = self._selected_job()
        if not job or not self._db:
            QMessageBox.information(
                self, "Supprimer", "Sélectionnez d’abord une vidéo."
            )
            return

        path = Path(job.output_path) if job.output_path else None
        has_file = bool(path and path.exists())

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Supprimer")
        box.setText(f"Supprimer « {job.clip_title} » de la liste ?")
        delete_file = QCheckBox("Supprimer aussi le fichier vidéo sur le disque")
        delete_file.setChecked(False)
        delete_file.setEnabled(has_file)
        if has_file:
            box.setInformativeText(str(path))
        box.setCheckBox(delete_file)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        if delete_file.isChecked() and path and path.exists():
            try:
                path.unlink()
            except OSError as exc:
                QMessageBox.warning(
                    self,
                    "Fichier",
                    f"Entrée retirée, mais le fichier n’a pas pu être effacé :\n{exc}",
                )
            # Related renders for same job id
            for suffix in ("_vertical.mp4", "_final.mp4"):
                sibling = path.parent / f"{job.id}{suffix}"
                if sibling.exists() and sibling != path:
                    try:
                        sibling.unlink()
                    except OSError:
                        pass
            thumb = get_app_root() / "temp" / f"jobthumb_{job.id}.jpg"
            try:
                thumb.unlink(missing_ok=True)
            except OSError:
                pass

        self._db.delete_job(job.id)
        self.refresh()
        self.log_requested.emit(f"Vidéo supprimée : {job.clip_title}")

    def _clear_all(self) -> None:
        if not self._db or not self._jobs:
            return
        reply = QMessageBox.question(
            self,
            "Tout vider",
            f"Supprimer les {len(self._jobs)} entrée(s) de « Mes vidéos » ?\n"
            "(Les fichiers sur le disque ne sont pas effacés.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        n = self._db.delete_all_jobs()
        self.refresh()
        self.log_requested.emit(f"Liste vidéos vidée ({n})")

    def _retry_selected(self) -> None:
        job = self._selected_job()
        if not job or not self._pipeline:
            return
        if job.output_path and Path(job.output_path).exists():
            self._start_publish(job)
            return
        QMessageBox.information(
            self,
            "Réessayer",
            "Pas de vidéo rendue — renvoyez le clip depuis Traitement.",
        )

    def _publish_selected(self) -> None:
        job = self._selected_job()
        if not job or not job.output_path or not Path(job.output_path).exists():
            QMessageBox.warning(
                self,
                "Publication",
                "Sélectionnez une vidéo déjà créée.",
            )
            return
        self._start_publish(job)

    def _start_publish(self, job: Job) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._worker = PublishJobWorker(self._pipeline, job)
        self._worker.log.connect(lambda m: self.log_requested.emit(m))
        self._worker.finished_ok.connect(lambda _j: self.refresh())
        self._worker.failed.connect(
            lambda m: QMessageBox.warning(self, "Publication", m)
        )
        self._worker.start()
        self.log_requested.emit(f"Publication : {job.clip_title}")

    def _schedule_selected(self) -> None:
        job = self._selected_job()
        if not job or not self._db:
            return
        if not job.output_path or not Path(job.output_path).exists():
            QMessageBox.information(
                self,
                "Planifier",
                "Il faut d’abord une vidéo créée.",
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Planifier la publication")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        tip = QLabel("Choisissez la date et l’heure de publication :")
        tip.setObjectName("PageSubtitle")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        edit = QDateTimeEdit(datetime.now())
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd/MM/yyyy HH:mm")
        lay.addWidget(edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        job.scheduled_at = edit.dateTime().toPython()
        job.status = JobStatus.QUEUED
        self._db.upsert_job(job)
        self.refresh()
        self.log_requested.emit(
            f"Planifié {job.clip_title} → {job.scheduled_at}"
        )

    def _selected_output_path(self) -> Optional[Path]:
        job = self._selected_job()
        if not job or not job.output_path:
            return None
        path = Path(job.output_path)
        return path if path.exists() else None

    def _open_selected_video(self) -> None:
        path = self._selected_output_path()
        if not path:
            QMessageBox.information(
                self,
                "Vidéo",
                "Sélectionnez une vidéo déjà créée.",
            )
            return
        try:
            os.startfile(str(path.resolve()))  # type: ignore[attr-defined]
        except Exception as exc:
            QMessageBox.warning(self, "Ouverture", str(exc))

    def _open_selected_folder(self) -> None:
        path = self._selected_output_path()
        if not path:
            QMessageBox.information(
                self,
                "Dossier",
                "Sélectionnez une vidéo déjà créée.",
            )
            return
        try:
            subprocess.run(["explorer", "/select,", str(path.resolve())], check=False)
        except Exception as exc:
            try:
                os.startfile(str(path.parent))  # type: ignore[attr-defined]
            except Exception:
                QMessageBox.warning(self, "Dossier", str(exc))
