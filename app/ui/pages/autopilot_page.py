"""Auto-pilot controls."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.utils.config import save_config


class AutopilotPage(QWidget):
    log_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scheduler = None
        self._config = None
        self._db = None
        self._build()

    def bind(self, scheduler, config, database) -> None:
        self._scheduler = scheduler
        self._config = config
        self._db = database
        self._load()
        scheduler.autopilot_tick.connect(self._on_tick)
        if config.get("auto_pilot", "enabled", default=False):
            self.status.setText("Actif (relancez Démarrer si besoin après redémarrage)")

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("Mode automatique")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        sub = QLabel(
            "L’appli peut chercher toute seule de nouveaux clips à heures régulières. "
            "Utile quand tout est déjà bien réglé. "
            "Sinon, restez sur les étapes 1-2-3 à la main."
        )
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(sub)

        box = QGroupBox("Réglages")
        form = QFormLayout(box)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 168)
        self.interval_spin.setSuffix(" h")
        self.interval_spin.setValue(6)
        form.addRow("Intervalle", self.interval_spin)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 50)
        self.limit_spin.setValue(5)
        form.addRow("Max publications / jour", self.limit_spin)
        root.addWidget(box)

        row = QHBoxLayout()
        self.start_btn = QPushButton("Démarrer")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("Arrêter")
        self.stop_btn.setObjectName("SecondaryButton")
        self.stop_btn.clicked.connect(self._stop)
        save_btn = QPushButton("Enregistrer")
        save_btn.setObjectName("SecondaryButton")
        save_btn.clicked.connect(self._save)
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        row.addWidget(save_btn)
        row.addStretch(1)
        root.addLayout(row)

        self.status = QLabel("Inactif")
        self.status.setObjectName("PageSubtitle")
        root.addWidget(self.status)

        self.quota = QLabel("")
        self.quota.setObjectName("PageSubtitle")
        root.addWidget(self.quota)

        root.addStretch(1)

    def _load(self) -> None:
        if not self._config:
            return
        self.interval_spin.setValue(
            int(self._config.get("auto_pilot", "interval_hours", default=6) or 6)
        )
        self.limit_spin.setValue(
            int(
                self._config.get("auto_pilot", "max_publications_per_day", default=5)
                or 5
            )
        )
        self._refresh_quota()

    def _save(self) -> None:
        if not self._config:
            return
        self._config.set("auto_pilot", "interval_hours", self.interval_spin.value())
        self._config.set(
            "auto_pilot", "max_publications_per_day", self.limit_spin.value()
        )
        save_config(self._config)
        self.log_requested.emit("Réglages auto-pilote enregistrés")
        QMessageBox.information(self, "Auto-pilote", "Réglages enregistrés.")

    def _start(self) -> None:
        self._save()
        if self._scheduler:
            self._scheduler.start_auto_pilot()
            self.status.setText("Actif ✓")
            self.log_requested.emit("Auto-pilote démarré")

    def _stop(self) -> None:
        if self._scheduler:
            self._scheduler.stop_auto_pilot()
            self.status.setText("Inactif")
            self.log_requested.emit("Auto-pilote arrêté")

    def _on_tick(self, message: str) -> None:
        self.status.setText(message)
        self._refresh_quota()

    def _refresh_quota(self) -> None:
        if not self._db or not self._config:
            return
        used = self._db.publications_today()
        limit = int(
            self._config.get("auto_pilot", "max_publications_per_day", default=5) or 5
        )
        self.quota.setText(f"Publications aujourd'hui : {used} / {limit}")
