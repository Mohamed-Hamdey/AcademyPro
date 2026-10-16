"""
First-run privacy consent dialog.

Shown once, on the very first launch. The user must accept to continue;
choosing "Quit" exits the app.

Once accepted, QSettings key `legal/privacy_accepted` is set to "true"
and the dialog never appears again.
"""

import sys

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QApplication,
)
from qtpy.QtCore import Qt, QSettings

from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING
from ui.i18n import t


_SETTINGS_ORG = "MembershipSystem"
_SETTINGS_APP = "app"
_SETTINGS_KEY = "legal/privacy_accepted"


def is_consent_given() -> bool:
    """True if the user has previously accepted the privacy notice."""
    s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    val = s.value(_SETTINGS_KEY, "false")
    return str(val).lower() in ("true", "1", "yes")


def mark_consent_given() -> None:
    s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    s.setValue(_SETTINGS_KEY, "true")
    s.sync()


class PrivacyConsentDialog(ThemedWidget, QDialog):
    """
    Modal dialog shown on first run. exec() returns Accepted if the
    user clicked "I accept". Anything else means they declined, and the
    caller should exit the app.
    """

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(t("privacy.title"))
        self.setModal(True)
        self.setMinimumSize(640, 520)
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        self.heading = QLabel(t("privacy.heading"))
        self.heading.setWordWrap(True)
        root.addWidget(self.heading)

        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setPlainText(t("privacy.body"))
        root.addWidget(self.body, stretch=1)

        self.footer = QLabel(t("privacy.footer"))
        self.footer.setWordWrap(True)
        root.addWidget(self.footer)

        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        button_row.addStretch()

        self.quit_button = QPushButton(t("privacy.btn.quit"))
        make_secondary(self.quit_button)
        self.quit_button.clicked.connect(self.reject)

        self.accept_button = QPushButton(t("privacy.btn.accept"))
        self.accept_button.setDefault(True)
        self.accept_button.clicked.connect(self._on_accept)

        button_row.addWidget(self.quit_button)
        button_row.addWidget(self.accept_button)
        root.addLayout(button_row)

    def _on_accept(self):
        mark_consent_given()
        self.accept()

    def restyle(self):
        tm = theme()
        self.heading.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 16px;"
            f"  font-weight: 700;"
            f"}}"
        )
        self.footer.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
        )


def ensure_privacy_consent() -> bool:
    """
    If consent was already given, return True immediately.
    Otherwise show the dialog. Return True if accepted, False if not.

    Called from main() before the app proceeds.
    """
    if is_consent_given():
        return True

    dlg = PrivacyConsentDialog(parent=None)
    result = dlg.exec()
    return result == QDialog.DialogCode.Accepted