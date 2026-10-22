"""
Player create/edit dialog — v5 design (matches users_dialog v5).

Header-style form, required-field asterisks, styled error banner,
flash guard during construction.
"""

import os
import sys
import logging

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QDateEdit, QPushButton, QHBoxLayout, QFileDialog, QLabel,
    QWidget, QFrame,QTimeEdit
)
from qtpy.QtCore import Qt, QDate,QTime

from ui.message_box import warn, error
from services import audit_service
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import load_config, get_group_label
from models.player import Player
from repositories import players_repo
from logic.qr_utils import generate_qr_for_player
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui import i18n


def _col(name: str, fallback_token: str, default: str) -> str:
    """Resolve a theme colour without ever raising."""
    try:
        pal = theme().palette()
        return pal.get(name) or pal.get(fallback_token) or default
    except Exception:
        return default


class _FieldLabel(QWidget):
    """Form label with a separate red asterisk for required fields."""

    def __init__(self, text: str, required: bool = True, parent=None):
        QWidget.__init__(self, parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        self.text_lbl = QLabel((text or "").rstrip(" *"), self)
        lay.addWidget(self.text_lbl)

        self.star_lbl = None
        if required:
            self.star_lbl = QLabel("*", self)
            lay.addWidget(self.star_lbl)
        lay.addStretch(1)
        self.apply_theme()

    def apply_theme(self):
        if self.star_lbl is not None:
            color = _col("danger", "danger", "#DC2626")
            self.star_lbl.setStyleSheet(
                f"QLabel {{ color: {color}; font-weight: 700; background: transparent; }}"
            )


class PlayerFormDialog(ThemedWidget, QDialog):
    def __init__(self, player=None, parent=None):
        QDialog.__init__(self, parent)

        # Flash guard.
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)

        try:
            self.editing_player = player
            self.setWindowTitle(
                t("dlg.player.title_edit") if player else t("dlg.player.title_add")
            )
            self.setMinimumWidth(520)
            self._selected_photo_path = player.photo_path if player else None

            self._build_ui()
            if player:
                self._prefill(player)
            self._init_theme()
        finally:
            self.setUpdatesEnabled(True)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
            self.update()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # ---- Text fields ----
        self.name_input = QLineEdit(self)

        self.national_id_input = QLineEdit(self)
        self.national_id_input.setMaxLength(14)

        self.phone_input = QLineEdit(self)

        # ---- DOB ----
        self.dob_input = QDateEdit(self)
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDisplayFormat("yyyy-MM-dd")
        self.dob_input.setDate(QDate(2015, 1, 1))
        
        # ---- Preferred Session Time ----
        self.session_time_combo = QComboBox(self)
        self.session_time_combo.addItem(t("dlg.player.session_time_none"), None)
        
        cfg = load_config()
        for time_val, time_info in cfg.get("session_times", {}).items():
            label = time_info.get("label_ar") if i18n.current_language() == "ar" else time_info.get("label")
            self.session_time_combo.addItem(label, time_val)
            
        self.session_time_combo.addItem(t("dlg.player.session_time_custom"), "__custom__")
        
        self.custom_time_input = QTimeEdit(self)
        self.custom_time_input.setDisplayFormat("HH:mm")
        self.custom_time_input.setTime(QTime(18, 0)) # default 6 PM
        self.custom_time_input.hide() # hidden by default
        
        self.session_time_combo.currentIndexChanged.connect(self._on_session_time_changed)


        
        # ---- Photo row ----
        self.photo_label = QLabel(t("dlg.player.no_photo"), self)
        photo_button = QPushButton(t("dlg.player.choose_photo"), self)
        make_secondary(photo_button)
        photo_button.clicked.connect(self._choose_photo)

        photo_row = QHBoxLayout()
        photo_row.setSpacing(SPACING["sm"])
        photo_row.setContentsMargins(0, 0, 0, 0)
        photo_row.addWidget(self.photo_label, stretch=1)
        photo_row.addWidget(photo_button)

        # ---- Form rows (with required asterisks) ----
        form.addRow(_FieldLabel(t("dlg.player.name"), True, self), self.name_input)
        form.addRow(_FieldLabel(t("dlg.player.national_id_optional"), False, self), self.national_id_input)
        form.addRow(_FieldLabel(t("dlg.player.phone"), True, self), self.phone_input)
        form.addRow(_FieldLabel(t("dlg.player.dob"), False, self), self.dob_input)
        form.addRow(_FieldLabel(t("dlg.player.session_time"), False, self), self.session_time_combo)
        form.addRow(_FieldLabel("", False, self), self.custom_time_input)
        form.addRow(_FieldLabel(t("dlg.player.photo"), False, self), photo_row)
        root.addLayout(form)

        # ---- Divider ----
        divider = QFrame(self)
        divider.setObjectName("playerFormDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            f"QFrame#playerFormDivider {{"
            f"  background-color: {_col('divider', 'border', '#E8EDF3')};"
            f"  border: none;"
            f"}}"
        )
        root.addWidget(divider)

        # ---- Error banner ----
        self.error_label = QLabel("", self)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

        # ---- Buttons ----
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        button_row.setContentsMargins(0, SPACING["sm"], 0, 0)

        cancel_button = QPushButton(t("dlg.player.cancel"), self)
        make_secondary(cancel_button)

        save_button = QPushButton(t("dlg.player.save"), self)
        save_button.setDefault(True)
        save_button.clicked.connect(self._on_save)
        cancel_button.clicked.connect(self.reject)

        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        root.addLayout(button_row)

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

    def _prefill(self, player):
        self.name_input.setText(player.full_name)
        self.national_id_input.setText(player.national_id or "")
        self.phone_input.setText(player.phone)
        try:
            y, m, d = (int(x) for x in player.dob.split("-"))
            self.dob_input.setDate(QDate(y, m, d))
        except Exception:
            pass
        if player.photo_path:
            self.photo_label.setText(os.path.basename(player.photo_path))
            
        # Handle session time loading
        if player.session_time:
            idx = self.session_time_combo.findData(player.session_time)
            if idx >= 0:
                self.session_time_combo.setCurrentIndex(idx)
            else:
                # It's a custom time
                idx = self.session_time_combo.findData("__custom__")
                self.session_time_combo.setCurrentIndex(idx)
                parts = player.session_time.split(":")
                if len(parts) == 2:
                    self.custom_time_input.setTime(QTime(int(parts[0]), int(parts[1])))
        else:
            self.session_time_combo.setCurrentIndex(0)

    def _on_session_time_changed(self, _idx):
        is_custom = self.session_time_combo.currentData() == "__custom__"
        self.custom_time_input.setVisible(is_custom)
    # ---------- photo ----------

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
        import time
        from paths import AppPaths

        photos_dir = AppPaths.photos_dir()
        try:
            chosen_abs = os.path.abspath(chosen_path)
            if chosen_abs.startswith(os.path.abspath(photos_dir)):
                return chosen_path
        except Exception:
            pass

        ext = os.path.splitext(chosen_path)[1] or ".jpg"
        filename = f"photo_{int(time.time() * 1000)}{ext}"
        dest = os.path.join(photos_dir, filename)

        try:
            shutil.copy2(chosen_path, dest)
            return dest
        except Exception as e:
            logging.getLogger(__name__).exception(
                "Could not copy player photo to app data folder: %s", e
            )
            return chosen_path

    # ---------- save ----------

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()

    def _on_save(self):
        self.error_label.hide()

        name = self.name_input.text().strip()
        national_id = self.national_id_input.text().strip() or None
        phone = self.phone_input.text().strip()

        if not name or not phone:
            self._show_error(t("dlg.player.missing_msg"))
            return

        dob = self.dob_input.date().toString("yyyy-MM-dd")

        if (self.editing_player
                and self._selected_photo_path == self.editing_player.photo_path):
            stored_photo_path = self.editing_player.photo_path
        else:
            stored_photo_path = self._persist_photo(self._selected_photo_path)
            
        # Determine session time
        session_time = self.session_time_combo.currentData()
        if session_time == "__custom__":
            session_time = self.custom_time_input.time().toString("HH:mm")
        elif session_time is None:
            session_time = None
            
        # ---- Edit mode ----
        if self.editing_player:
            self.editing_player.full_name = name
            self.editing_player.national_id = national_id
            self.editing_player.phone = phone
            self.editing_player.dob = dob
            self.editing_player.photo_path = stored_photo_path
            self.editing_player.session_time = session_time
            try:
                players_repo.update(self.editing_player)
                audit_service.player_updated(
                    player_id=self.editing_player.player_id,
                    name=self.editing_player.full_name,
                )
            except Exception as e:
                self._show_error(str(e))
                return
            self.saved_player_id = self.editing_player.player_id
            


        # ---- Create mode ----
        else:
            new_player = Player(
                player_id=None,
                full_name=name,
                national_id=national_id or None,
                phone=phone,
                dob=dob,
                photo_path=stored_photo_path,
                qr_code_path=None,
                session_time=session_time,
            )
            try:
                self.saved_player_id = players_repo.create(new_player)
            except Exception as e:
                self._show_error(
                    t("dlg.player.save_failed_duplicate", error=e)
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