"""Dialogs for online update check results."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.services.updater import UpdateInfo, open_update_page


class UpdateAvailableDialog(QDialog):
    def __init__(self, info: UpdateInfo, parent=None) -> None:
        super().__init__(parent)
        self._info = info
        self.setWindowTitle("Mise à jour disponible")
        self.setMinimumWidth(460)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setSpacing(12)

        title = QLabel(
            f"Clip2Tube {info.latest_version} est disponible "
            f"(vous avez {info.current_version})."
        )
        title.setObjectName("HomeSectionTitle")
        title.setWordWrap(True)
        root.addWidget(title)

        hint = QLabel(
            "Téléchargez le ZIP portable, fermez Clip2Tube, "
            "remplacez le dossier de l’appli, puis relancez. "
            "Vos fichiers config/ et data/ sont à garder."
        )
        hint.setObjectName("PageSubtitle")
        hint.setWordWrap(True)
        root.addWidget(hint)

        if info.notes:
            notes = QTextEdit()
            notes.setReadOnly(True)
            notes.setPlainText(info.notes)
            notes.setFixedHeight(160)
            root.addWidget(notes)

        buttons = QDialogButtonBox()
        open_btn = QPushButton("Télécharger / ouvrir la page")
        open_btn.clicked.connect(self._open)
        later_btn = QPushButton("Plus tard")
        later_btn.setObjectName("SecondaryButton")
        later_btn.clicked.connect(self.reject)
        buttons.addButton(open_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(later_btn, QDialogButtonBox.ButtonRole.RejectRole)
        root.addWidget(buttons)

    def _open(self) -> None:
        if open_update_page(self._info):
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Lien manquant",
                "Aucune URL de téléchargement. Vérifiez la release GitHub.",
            )


def show_update_result(
    parent,
    info: UpdateInfo,
    *,
    silent_if_up_to_date: bool = False,
) -> None:
    """Show the right message for an UpdateInfo result."""
    if info.error:
        if silent_if_up_to_date:
            return
        QMessageBox.warning(parent, "Mise à jour", info.error)
        return

    if info.available:
        UpdateAvailableDialog(info, parent).exec()
        return

    if silent_if_up_to_date:
        return

    QMessageBox.information(
        parent,
        "À jour",
        f"Vous avez déjà la dernière version ({info.current_version}).",
    )
