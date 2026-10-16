"""
Change password dialog — v4 design.

Used in two contexts:
  * Forced change after first-run bootstrap (force=True)
  * Voluntary change from a "My account" menu (force=False)
"""

import os
import sys

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QHBoxLayout, QLabel,
)
from services import audit_service
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import auth_service
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


class ChangePasswordDialog(ThemedWidget, QDialog):
    def __init__(self, user, force=False, parent=None):
        QDialog.__init__(self, parent)
        self.user = user
        self.force = force
        self.setWindowTitle(t("login.change.title"))
        self.setModal(True)
        self.setMinimumWidth(400)

        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        if self.force:
            self.hint = QLabel(t("login.change.forced_hint"))
            self.hint.setWordWrap(True)
            layout.addWidget(self.hint)

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])

        self.new_input = QLineEdit()
        self.new_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow(t("login.change.new_password"), self.new_input)
        form.addRow(t("login.change.confirm_password"), self.confirm_input)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        if not self.force:
            cancel_button = QPushButton(t("login.change.cancel"))
            make_secondary(cancel_button)
            cancel_button.clicked.connect(self.reject)
            button_row.addWidget(cancel_button)
        button_row.addStretch()
        save_button = QPushButton(t("login.change.save"))
        save_button.setDefault(True)
        save_button.clicked.connect(self._on_save)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    def restyle(self):
        tm = theme()
        self.error_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('danger')};"
            f"  background-color: {tm.color('danger_soft')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 8px 12px;"
            f"}}"
        )
        if self.force:
            self.hint.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('warning')};"
                f"  background-color: {tm.color('warning_soft')};"
                f"  border-radius: {RADIUS['sm']}px;"
                f"  padding: 8px 12px;"
                f"}}"
            )

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()

    def _on_save(self):
        new_pw = self.new_input.text()
        confirm = self.confirm_input.text()

        if not new_pw:
            self._show_error(t("login.change.error.empty"))
            return
        if new_pw != confirm:
            self._show_error(t("login.change.error.mismatch"))
            return
        if len(new_pw) < 4:
            self._show_error(t("login.change.error.too_short"))
            return

        try:
            auth_service.change_password(self.user.user_id, new_pw)
                   
            from repositories import users_repo
            updated = users_repo.get_by_id(self.user.user_id)
            if updated is not None:
                self.user.password_hash = updated.password_hash
        except Exception as e:
            self._show_error(str(e))
            return

        # The user object in memory has a stale hash; refresh it.
        from repositories import users_repo
        updated = users_repo.get_by_id(self.user.user_id)
        if updated is not None:
            self.user.password_hash = updated.password_hash
        # Audit: was this the user changing their own password, or an admin?
        from app_state import app as app_state
        by_admin = app_state.user is not None and app_state.user.user_id != self.user.user_id
        audit_service.user_password_changed(
            user_id=self.user.user_id,
            username=self.user.username,
            by_admin=by_admin,
        )
        self.accept()