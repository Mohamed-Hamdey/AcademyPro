"""Player create/edit dialog — v4 design."""

import os
import sys

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QDateEdit, QPushButton, QHBoxLayout, QFileDialog, QLabel,
)
from qtpy.QtCore import QDate

from ui.message_box import warn, error
from services import audit_service
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import load_config, get_group_label
from models.player import Player
from repositories import players_repo
from logic.qr_utils import generate_qr_for_player
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING
from ui.i18n import t


class PlayerFormDialog(ThemedWidget, QDialog):
    def __init__(self, player=None, parent=None):
        QDialog.__init__(self, parent)
        self.editing_player = player
        self.setWindowTitle(
            t("dlg.player.title_edit") if player else t("dlg.player.title_add")
        )
        self.setMinimumWidth(420)
        self._selected_photo_path = player.photo_path if player else None
        self._build_ui()
        if player:
            self._prefill(player)
        self._init_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])
        form.setLabelAlignment(form.labelAlignment())

        self.name_input = QLineEdit()
        self.national_id_input = QLineEdit()
        self.national_id_input.setMaxLength(14)
        self.phone_input = QLineEdit()

        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDisplayFormat("yyyy-MM-dd")
        self.dob_input.setDate(QDate(2015, 1, 1))



        # Photo row — filename label + choose button
        self.photo_label = QLabel(t("dlg.player.no_photo"))
        photo_button = QPushButton(t("dlg.player.choose_photo"))
        make_secondary(photo_button)
        photo_button.clicked.connect(self._choose_photo)
        photo_row = QHBoxLayout()
        photo_row.setSpacing(SPACING["sm"])
        photo_row.addWidget(self.photo_label, stretch=1)
        photo_row.addWidget(photo_button)

        form.addRow(t("dlg.player.name"), self.name_input)
        form.addRow(t("dlg.player.national_id_optional"), self.national_id_input)
        form.addRow(t("dlg.player.phone"), self.phone_input)
        form.addRow(t("dlg.player.dob"), self.dob_input)
        form.addRow(t("dlg.player.photo"), photo_row)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        cancel_button = QPushButton(t("dlg.player.cancel"))
        make_secondary(cancel_button)
        save_button = QPushButton(t("dlg.player.save"))
        save_button.setDefault(True)
        save_button.clicked.connect(self._on_save)
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    def restyle(self):
        tm = theme()
        self.photo_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
        )

    def _prefill(self, player):
        self.name_input.setText(player.full_name)
        self.national_id_input.setText(player.national_id or "")
        self.phone_input.setText(player.phone)
        y, m, d = (int(x) for x in player.dob.split("-"))
        self.dob_input.setDate(QDate(y, m, d))
        if player.photo_path:
            self.photo_label.setText(os.path.basename(player.photo_path))

    def _choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("dlg.player.select_photo_title"), "",
            t("dlg.player.images_filter")
        )
        if path:
            self._selected_photo_path = path
            self.photo_label.setText(os.path.basename(path))

    def _persist_photo(self, chosen_path):
        if not chosen_path:
            return None

        import shutil
        from paths import AppPaths
        photos_dir = AppPaths.photos_dir()
        try:
            chosen_abs = os.path.abspath(chosen_path)
            if chosen_abs.startswith(os.path.abspath(photos_dir)):
                return chosen_path
        except Exception:
            pass

        import time
        ext = os.path.splitext(chosen_path)[1] or ".jpg"
        filename = f"photo_{int(time.time() * 1000)}{ext}"
        dest = os.path.join(photos_dir, filename)

        try:
            shutil.copy2(chosen_path, dest)
            return dest
        except Exception as e:
            print(f"Warning: could not copy photo to app data folder: {e}")
            return chosen_path

    def _on_save(self):
        name = self.name_input.text().strip()
        national_id = self.national_id_input.text().strip() or None
        phone = self.phone_input.text().strip()

        if not name or not phone:
            warn(self, t("dlg.player.missing_title"), t("dlg.player.missing_msg"))
            return

        dob = self.dob_input.date().toString("yyyy-MM-dd")

        if self.editing_player and self._selected_photo_path == self.editing_player.photo_path:
            stored_photo_path = self.editing_player.photo_path
        else:
            stored_photo_path = self._persist_photo(self._selected_photo_path)

        if self.editing_player:
            self.editing_player.full_name = name
            self.editing_player.national_id = national_id
            self.editing_player.phone = phone
            self.editing_player.dob = dob
            self.editing_player.photo_path = stored_photo_path
            try:
                players_repo.update(self.editing_player)
                audit_service.player_updated(
                player_id=self.editing_player.player_id,
                name=self.editing_player.full_name,
            )
            except Exception as e:
                error(self, t("dlg.player.save_failed"), str(e))
                return
            self.saved_player_id = self.editing_player.player_id
        else:
            new_player = Player(
                player_id=None,
                full_name=name,
                national_id=national_id or None,
                phone=phone,
                dob=dob,
                photo_path=stored_photo_path,
                qr_code_path=None,
            )
            try:
                self.saved_player_id = players_repo.create(new_player)
            except Exception as e:
                error(
                    self, t("dlg.player.save_failed"),
                    t("dlg.player.save_failed_duplicate", error=e),
                )
                return
            qr_path = generate_qr_for_player(self.saved_player_id)
            new_player.player_id = self.saved_player_id
            new_player.qr_code_path = qr_path
            players_repo.update(new_player)
            audit_service.player_created(
                player_id=new_player.player_id,
                name=new_player.full_name,
            )
            self.newly_created_qr_path = qr_path

        self.accept()