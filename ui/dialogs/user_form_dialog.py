"""
Add / edit user dialog — v4 design.

Create mode:
    Photo, Username, Display name, Password + confirm, Role

Edit mode:
    Photo, Username (read-only), Display name, Role, Active checkbox

Safety checks live here for the "last manager" constraints.
"""

import os
import sys

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QPushButton,
    QHBoxLayout, QLabel, QFileDialog, QCheckBox, QMessageBox,
)
from qtpy.QtCore import Qt
from services import audit_service
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import users_repo
from services import auth_service
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t
from paths import AppPaths


class UserFormDialog(ThemedWidget, QDialog):
    def __init__(self, user=None, is_last_manager=False, parent=None):
        QDialog.__init__(self, parent)
        self.editing_user = user
        self.is_last_manager = is_last_manager
        self.setWindowTitle(
            t("users.dialog.title_edit") if user else t("users.dialog.title_add")
        )
        self.setMinimumWidth(460)
        self._selected_photo_path = user.photo_path if user else None
        self._build_ui()
        if user:
            self._prefill(user)
        self._init_theme()

    # ---------- UI ----------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])

        # ---- Photo row ----
        self.photo_label = QLabel(t("users.dialog.no_photo"))
        photo_button = QPushButton(t("users.dialog.choose_photo"))
        make_secondary(photo_button)
        photo_button.clicked.connect(self._choose_photo)
        photo_row = QHBoxLayout()
        photo_row.setSpacing(SPACING["sm"])
        photo_row.addWidget(self.photo_label, stretch=1)
        photo_row.addWidget(photo_button)

        # ---- Text fields ----
        self.username_input = QLineEdit()
        self.display_name_input = QLineEdit()

        # Password fields (create mode only)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_confirm_input = QLineEdit()
        self.password_confirm_input.setEchoMode(QLineEdit.EchoMode.Password)

        # Role dropdown — Arabic · English
        self.role_input = QComboBox()
        self.role_input.addItem(
            f"المدير · Manager", "manager"
        )
        self.role_input.addItem(
            f"موظف الاستقبال · Receptionist", "receptionist"
        )

        # Active checkbox (edit mode only)
        self.active_checkbox = QCheckBox(t("users.dialog.active_label"))

        form.addRow(t("users.dialog.photo"), photo_row)
        form.addRow(t("users.dialog.username"), self.username_input)
        form.addRow(t("users.dialog.display_name"), self.display_name_input)

        if not self.editing_user:
            form.addRow(t("users.dialog.password"), self.password_input)
            form.addRow(t("users.dialog.password_confirm"), self.password_confirm_input)

        form.addRow(t("users.dialog.role"), self.role_input)

        if self.editing_user:
            form.addRow("", self.active_checkbox)

        layout.addLayout(form)

        # Error display
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        cancel_button = QPushButton(t("users.dialog.cancel"))
        make_secondary(cancel_button)
        save_button = QPushButton(t("users.dialog.save"))
        save_button.setDefault(True)
        save_button.clicked.connect(self._on_save)
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    # ---------- theming ----------

    def restyle(self):
        tm = theme()
        self.photo_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
        )
        self.error_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('danger')};"
            f"  background-color: {tm.color('danger_soft')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 8px 12px;"
            f"}}"
        )

    # ---------- prefill ----------

    def _prefill(self, user):
        self.username_input.setText(user.username)
        self.username_input.setReadOnly(True)
        self.username_input.setStyleSheet(
            f"QLineEdit {{"
            f"  color: {theme().color('text_secondary')};"
            f"  background-color: {theme().color('surface_alt')};"
            f"}}"
        )
        self.display_name_input.setText(user.display_name)

        idx = self.role_input.findData(user.role)
        if idx >= 0:
            self.role_input.setCurrentIndex(idx)

        self.active_checkbox.setChecked(user.active)

        # If this user is the last active manager, disable role change and
        # the deactivate checkbox — the app can't afford to lose them.
        if self.is_last_manager:
            self.active_checkbox.setChecked(True)
            self.active_checkbox.setEnabled(False)
            idx = self.role_input.findData("manager")
            if idx >= 0:
                self.role_input.setCurrentIndex(idx)
            self.role_input.setEnabled(False)

            hint = QLabel(t("users.dialog.last_manager_hint"))
            hint.setWordWrap(True)
            hint.setStyleSheet(
                f"QLabel {{"
                f"  color: {theme().color('warning')};"
                f"  background-color: {theme().color('warning_soft')};"
                f"  border-radius: {RADIUS['sm']}px;"
                f"  padding: 8px 12px;"
                f"}}"
            )
            self.layout().insertWidget(1, hint)

        if user.photo_path:
            self.photo_label.setText(os.path.basename(user.photo_path))

    # ---------- photo ----------

    def _choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("users.dialog.select_photo_title"), "",
            t("dlg.player.images_filter")
        )
        if path:
            self._selected_photo_path = path
            self.photo_label.setText(os.path.basename(path))

    def _persist_photo(self, chosen_path, username: str):
        """Copy the chosen photo into the app's data folder, return the new path."""
        if not chosen_path:
            return None
        import shutil
        import time

        photos_dir = AppPaths.photos_dir()
        try:
            chosen_abs = os.path.abspath(chosen_path)
            if chosen_abs.startswith(os.path.abspath(photos_dir)):
                return chosen_path
        except Exception:
            pass

        ext = os.path.splitext(chosen_path)[1] or ".jpg"
        filename = f"user_{username}_{int(time.time() * 1000)}{ext}"
        dest = os.path.join(photos_dir, filename)
        try:
            shutil.copy2(chosen_path, dest)
            return dest
        except Exception as e:
            print(f"Warning: could not copy user photo: {e}")
            return chosen_path

    # ---------- save ----------

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()

    def _on_save(self):
        self.error_label.hide()

        username = self.username_input.text().strip()
        display_name = self.display_name_input.text().strip()
        role = self.role_input.currentData()

        if not display_name:
            self._show_error(t("users.dialog.error.display_name_required"))
            return

        # ---- Edit mode ----
        if self.editing_user:
            # Last-manager safety (belt and braces — dialog also locks the fields)
            if self.is_last_manager and role != "manager":
                self._show_error(t("users.error.last_manager_msg"))
                return

            photo_path = self._persist_photo(
                self._selected_photo_path, self.editing_user.username
            ) if self._selected_photo_path != self.editing_user.photo_path \
              else self.editing_user.photo_path

            updated = self.editing_user
            updated.display_name = display_name
            updated.role = role
            updated.active = self.active_checkbox.isChecked()
            updated.photo_path = photo_path

            try:
                users_repo.update(updated)
                audit_service.user_updated(
                user_id=updated.user_id,
                username=updated.username,
                changes={
                    "display_name": updated.display_name,
                    "role": updated.role,
                    "active": updated.active,
                },
            )
            except Exception as e:
                self._show_error(str(e))
                return

            self.accept()
            return

        # ---- Create mode ----
        password = self.password_input.text()
        password_confirm = self.password_confirm_input.text()

        if not username:
            self._show_error(t("users.dialog.error.username_required"))
            return
        if not password:
            self._show_error(t("users.dialog.error.password_required"))
            return
        if password != password_confirm:
            self._show_error(t("users.dialog.error.password_mismatch"))
            return
        if len(password) < 4:
            self._show_error(t("users.dialog.error.password_too_short"))
            return

        photo_path = self._persist_photo(self._selected_photo_path, username)

        try:
            new_user_id = auth_service.create_user(
                username=username,
                display_name=display_name,
                password=password,
                role=role,
                photo_path=photo_path,
            )
        except Exception as e:
            self._show_error(str(e))
            return

        audit_service.user_created(user_id=new_user_id, username=username)

        self.accept()