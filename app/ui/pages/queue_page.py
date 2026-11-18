"""Publication queue with status and retry."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QDateTimeEdit,
)

from app.models import Job, JobStatus
from app.ui.workers import PublishJobWorker


class QueuePage(QWidget):
    log_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._db = None
        self._pipeline = None
        self._worker: Optional[PublishJobWorker] = None
        self._build()

    def bind(self, database, pipeline) -> None:
        self._db = database
        self._pipeline = pipeline
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        badge = QLabel("Étape 3")
        badge.setObjectName("StepBadge")
        badge.setMaximumWidth(90)
        root.addWidget(badge)

        title = QLabel("Mes vidéos")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        sub = QLabel(
            "Ici vous voyez où en est chaque vidéo. "
            "Sélectionnez une ligne, puis Publier, Planifier ou Réessayer."
        )
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(sub)

        tools = QHBoxLayout()
        refresh = QPushButton("Rafraîchir la liste")
        refresh.setObjectName("SecondaryButton")
        refresh.clicked.connect(self.refresh)
        tools.addWidget(refresh)

        self.retry_btn = QPushButton("Réessayer")
        self.retry_btn.setObjectName("SecondaryButton")
        self.retry_btn.clicked.connect(self._retry_selected)
        tools.addWidget(self.retry_btn)

        self.publish_btn = QPushButton("Publier maintenant")
        self.publish_btn.setObjectName("BigAction")
        self.publish_btn.clicked.connect(self._publish_selected)
        tools.addWidget(self.publish_btn)

        self.schedule_btn = QPushButton("Choisir une date…")
        self.schedule_btn.setObjectName("SecondaryButton")
        self.schedule_btn.clicked.connect(self._schedule_selected)
        tools.addWidget(self.schedule_btn)

        self.open_btn = QPushButton("Ouvrir la vidéo")
        self.open_btn.setObjectName("SecondaryButton")
        self.open_btn.clicked.connect(self._open_selected_video)
        tools.addWidget(self.open_btn)

        self.folder_btn = QPushButton("📁 Emplacement")
        self.folder_btn.setObjectName("SecondaryButton")
        self.folder_btn.clicked.connect(self._open_selected_folder)
        tools.addWidget(self.folder_btn)

        tools.addStretch(1)
        root.addLayout(tools)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Titre",
                "Streamer",
                "État",
                "Avancement",
                "Programmée",
                "YouTube",
                "Message",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        if not self._db:
            return
        jobs = self._db.list_jobs(200)
        self.table.setRowCount(0)
        for job in jobs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                job.clip_title,
                job.streamer,
                job.status.value,
                f"{int(job.progress)}%",
                job.scheduled_at.strftime("%Y-%m-%d %H:%M") if job.scheduled_at else "—",
                job.youtube_video_id or "—",
                (job.error_message or "")[:80],
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, job.id)
                self.table.setItem(row, col, item)

    def _selected_job_id(self) -> Optional[str]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _retry_selected(self) -> None:
        job_id = self._selected_job_id()
        if not job_id or not self._db or not self._pipeline:
            return
        job = self._db.get_job(job_id)
        if not job:
            return
        if job.output_path:
            self._start_publish(job)
        else:
            QMessageBox.information(
                self,
                "Réessayer",
                "Pas de vidéo rendue — renvoyez le clip depuis Traitement.",
            )

    def _publish_selected(self) -> None:
        job_id = self._selected_job_id()
        if not job_id or not self._db:
            return
        job = self._db.get_job(job_id)
        if not job or not job.output_path:
            QMessageBox.warning(self, "Publication", "Job sans fichier vidéo.")
            return
        self._start_publish(job)

    def _start_publish(self, job: Job) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._worker = PublishJobWorker(self._pipeline, job)
        self._worker.log.connect(lambda m: self.log_requested.emit(m))
        self._worker.finished_ok.connect(lambda j: self.refresh())
        self._worker.failed.connect(
            lambda m: QMessageBox.warning(self, "Publication", m)
        )
        self._worker.start()
        self.log_requested.emit(f"Publication: {job.clip_title}")

    def _schedule_selected(self) -> None:
        job_id = self._selected_job_id()
        if not job_id or not self._db:
            return
        job = self._db.get_job(job_id)
        if not job:
            return

        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout as QV

        dlg = QDialog(self)
        dlg.setWindowTitle("Planifier la publication")
        lay = QV(dlg)
        lay.addWidget(QLabel("Date et heure (locale) :"))
        edit = QDateTimeEdit(datetime.now())
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd HH:mm")
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
        job_id = self._selected_job_id()
        if not job_id or not self._db:
            return None
        job = self._db.get_job(job_id)
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
                "Sélectionnez une ligne qui a déjà une vidéo créée.",
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
                "Sélectionnez une ligne qui a déjà une vidéo créée.",
            )
            return
        try:
            subprocess.run(["explorer", "/select,", str(path.resolve())], check=False)
        except Exception as exc:
            try:
                os.startfile(str(path.parent))  # type: ignore[attr-defined]
            except Exception:
                QMessageBox.warning(self, "Dossier", str(exc))
