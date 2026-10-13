"""
Login screen — v4 design.

Shown as a modal dialog before the main window opens. On successful
authentication, stores the user in `app_state.app` and accepts.
"""

import os
import sys

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_academy_name, get_academy_logo, load_config
from services import auth_service
from app_state import app as app_state
from ui import i18n
from ui.theme import theme, ThemedWidget
from ui.design import SPACING, RADIUS, TYPOGRAPHY
from ui.i18n import t


class LoginDialog(ThemedWidget, QDialog):
    """
    Modal login dialog. exec() returns QDialog.Accepted on success.
    The authenticated user is stored in app_state.app.
    """

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(t("login.title"))
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setMinimumHeight(480)
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["2xl"], SPACING["xl"], SPACING["2xl"], SPACING["xl"]
        )
        layout.setSpacing(SPACING["md"])
        layout.addStretch()

        # ---- Logo ----
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(96, 96)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_logo()
        layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # ---- Academy name ----
        self.academy_label = QLabel()
        self.academy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.academy_label.setWordWrap(True)
        layout.addWidget(self.academy_label)

        layout.addSpacing(SPACING["lg"])

        # ---- Username ----
        self.username_label = QLabel(t("login.username"))
        self.username_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.username_label)

        self.username_input = QLineEdit()
        self.username_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.username_input.returnPressed.connect(self._on_submit)
        layout.addWidget(self.username_input)

        layout.addSpacing(SPACING["xs"])

        # ---- Password ----
        self.password_label = QLabel(t("login.password"))
        self.password_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.password_label)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.password_input.returnPressed.connect(self._on_submit)
        layout.addWidget(self.password_input)

        layout.addSpacing(SPACING["md"])

        # ---- Error message (hidden by default) ----
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # ---- Submit button ----
        self.submit_button = QPushButton(t("login.submit"))
        self.submit_button.setDefault(True)
        self.submit_button.setMinimumHeight(40)
        self.submit_button.clicked.connect(self._on_submit)
        layout.addWidget(self.submit_button)

        layout.addStretch()

    def _load_logo(self):
        path = get_academy_logo()
        if path:
            pix = QPixmap(path).scaled(
                96, 96,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(pix)
        else:
            initials = "".join(w[0] for w in get_academy_name().split()[:3]).upper()
            self.logo_label.setText(initials or "A")

    # ---------- theming ----------

    def restyle(self):
        tm = theme()

        # Logo badge — only if it's a monogram (no pixmap)
        if self.logo_label.pixmap() is None or self.logo_label.pixmap().isNull():
            self.logo_label.setStyleSheet(
                f"QLabel {{"
                f"  background-color: {tm.color('primary')};"
                f"  color: {tm.color('text_on_primary')};"
                f"  font-size: 36px; font-weight: 700;"
                f"  border-radius: {RADIUS['lg']}px;"
                f"}}"
            )

        cfg = load_config()
        if i18n.current_language() == "ar":
            name = cfg.get("academy_name_ar") or cfg.get("academy_name", "")
        else:
            name = cfg.get("academy_name", "")
        self.academy_label.setText(name)
        self.academy_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['section']['size']}px;"
            f"  font-weight: 600;"
            f"}}"
        )

        for lbl in (self.username_label, self.password_label):
            lbl.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text_secondary')};"
                f"  background-color: transparent;"
                f"  font-size: {TYPOGRAPHY['label']['size']}px;"
                f"  font-weight: 600;"
                f"}}"
            )

        self.error_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('danger')};"
            f"  background-color: {tm.color('danger_soft')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 8px 12px;"
            f"  font-size: {TYPOGRAPHY['body']['size']}px;"
            f"}}"
        )

    # ---------- submit ----------

    def _show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()

    def _clear_error(self):
        self.error_label.setText("")
        self.error_label.hide()

    def _on_submit(self):
        self._clear_error()

        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self._show_error(t("login.error.empty_fields"))
            return

        result = auth_service.login(username, password)

        if result.status == "bad_credentials":
            self._show_error(t("login.error.bad_credentials"))
            self.password_input.clear()
            return

        if result.status == "inactive":
            self._show_error(t("login.error.inactive"))
            return

        if result.status == "bootstrap":
            # Accept the default password but force a change first.
            from ui.screens.change_password_dialog import ChangePasswordDialog
            changer = ChangePasswordDialog(
                result.user,
                force=True,
                parent=self,
            )
            if changer.exec() != QDialog.DialogCode.Accepted:
                # User cancelled the forced change — bail out.
                return
            # Password changed; re-fetch the user (its hash is now real).
            user = result.user
            app_state.set_user(user)
            self.accept()
            return

        # Normal successful login
        app_state.set_user(result.user)
        self.accept()