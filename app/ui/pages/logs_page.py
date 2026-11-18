"""Live application logs."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LogsPage(QWidget):
    clear_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._db = None
        self._build()

    def bind(self, database) -> None:
        self._db = database
        self.reload_from_db()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        title = QLabel("Journal")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        tip = QLabel(
            "Messages techniques de l’appli. Utile si quelque chose bloque — "
            "vous pouvez copier le texte pour demander de l’aide."
        )
        tip.setObjectName("PageSubtitle")
        tip.setWordWrap(True)
        root.addWidget(tip)

        tools = QHBoxLayout()
        refresh = QPushButton("Actualiser")
        refresh.setObjectName("SecondaryButton")
        refresh.clicked.connect(self.reload_from_db)
        clear = QPushButton("Vider le journal")
        clear.setObjectName("SecondaryButton")
        clear.clicked.connect(self._clear)
        tools.addWidget(refresh)
        tools.addWidget(clear)
        tools.addStretch(1)
        root.addLayout(tools)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName("LogLabel")
        root.addWidget(self.console, stretch=1)

    def append(self, message: str, level: str = "INFO") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.console.appendPlainText(f"[{stamp}] [{level}] {message}")
        if self._db:
            try:
                self._db.add_log(level, "ui", message)
            except Exception:
                pass

    def reload_from_db(self) -> None:
        if not self._db:
            return
        self.console.clear()
        for row in reversed(self._db.list_logs(300)):
            self.console.appendPlainText(
                f"[{row['created_at'][11:19]}] [{row['level']}] "
                f"{row['source']}: {row['message']}"
            )

    def _clear(self) -> None:
        self.console.clear()
        if self._db:
            self._db.clear_logs()
        self.clear_requested.emit()
