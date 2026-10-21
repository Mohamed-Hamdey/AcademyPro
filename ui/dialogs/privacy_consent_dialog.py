"""
First-run privacy consent dialog — v5 polish.

Shown once, on the very first launch. The user must accept to continue;
choosing "Quit" exits the app.

Once accepted, QSettings key `legal/privacy_accepted` is set to "true"
and the dialog never appears again.

Design v5 polish:
  * Wider (720×620).
  * Header block with heading + body-style restyled QTextEdit.
  * Divider before the footer caption.
  * WA_DontShowOnScreen flash guard during construction.
"""

import sys

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QApplication, QFrame,
)
from qtpy.QtCore import Qt, QSettings

from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS, TYPOGRAPHY
from ui.i18n import t


_SETTINGS_ORG = "MembershipSystem"
_SETTINGS_APP = "app"
_SETTINGS_KEY = "legal/privacy_accepted"


def _col(name: str, fallback_token: str, default: str) -> str:
    """Resolve a theme colour without ever raising."""
    try:
        pal = theme().palette()
        return pal.get(name) or pal.get(fallback_token) or default
    except Exception:
        return default


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

        # Flash guard.
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)

        try:
            self.setWindowTitle(t("privacy.title"))
            self.setModal(True)
            self.setMinimumSize(720, 620)
            self._build_ui()
            self._init_theme()
        finally:
            self.setUpdatesEnabled(True)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
            self.update()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        # ---- Header ----
        self.heading = QLabel(t("privacy.heading"), self)
        self.heading.setWordWrap(True)
        root.addWidget(self.heading)

        # ---- Divider ----
        divider_top = QFrame(self)
        divider_top.setObjectName("privacyDividerTop")
        divider_top.setFixedHeight(1)
        divider_top.setStyleSheet(
            f"QFrame#privacyDividerTop {{"
            f"  background-color: {_col('divider', 'border', '#E8EDF3')};"
            f"  border: none;"
            f"}}"
        )
        root.addWidget(divider_top)

        # ---- Body ----
        self.body = QTextEdit(self)
        self.body.setReadOnly(True)
        self.body.setPlainText(t("privacy.body"))
        root.addWidget(self.body, stretch=1)

        # ---- Divider ----
        divider_bottom = QFrame(self)
        divider_bottom.setObjectName("privacyDividerBottom")
        divider_bottom.setFixedHeight(1)
        divider_bottom.setStyleSheet(
            f"QFrame#privacyDividerBottom {{"
            f"  background-color: {_col('divider', 'border', '#E8EDF3')};"
            f"  border: none;"
            f"}}"
        )
        root.addWidget(divider_bottom)

        # ---- Footer caption ----
        self.footer = QLabel(t("privacy.footer"), self)
        self.footer.setWordWrap(True)
        root.addWidget(self.footer)

        # ---- Buttons ----
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        button_row.setContentsMargins(0, SPACING["sm"], 0, 0)
        button_row.addStretch()

        self.quit_button = QPushButton(t("privacy.btn.quit"), self)
        make_secondary(self.quit_button)
        self.quit_button.clicked.connect(self.reject)

        self.accept_button = QPushButton(t("privacy.btn.accept"), self)
        self.accept_button.setDefault(True)
        self.accept_button.clicked.connect(self._on_accept)

        button_row.addWidget(self.quit_button)
        button_row.addWidget(self.accept_button)
        root.addLayout(button_row)

    def _on_accept(self):
        mark_consent_given()
        self.accept()

    # ---------- theming ----------

    def restyle(self):
        tm = theme()

        self.heading.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['section']['size']}px;"
            f"  font-weight: 700;"
            f"}}"
        )
        self.body.setStyleSheet(
            f"QTextEdit {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"  color: {tm.color('text')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['md']}px;"
            f"  padding: 12px 14px;"
            f"  font-size: 13px;"
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