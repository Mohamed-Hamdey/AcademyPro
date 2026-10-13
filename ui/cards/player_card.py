"""
Player card widget — v4 design.

Used in two places:
  * Scan result (after a check-in) — includes a status pill
  * Player detail overview — no pill

Public API is unchanged:
    card.display_player(player, subscription, check_in_state)
    card.clear()
    card.set_photo(path_or_None)
"""

import os
import sys

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QFrame,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_plan_label
from ui.components import Pill
from ui.theme import theme, ThemedWidget
from ui.design import SPACING, RADIUS, TYPOGRAPHY
from ui.i18n import t


PHOTO_SIZE = 120


class PlayerCardWidget(QFrame, ThemedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playerCard")
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        outer.setSpacing(SPACING["lg"])

        # ---- Photo ----
        self.photo_label = QLabel()
        self.photo_label.setFixedSize(PHOTO_SIZE, PHOTO_SIZE)
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setText("👤")   # glyph placeholder, styled larger below
        outer.addWidget(self.photo_label, alignment=Qt.AlignmentFlag.AlignTop)

        # ---- Info column ----
        info_col = QVBoxLayout()
        info_col.setSpacing(SPACING["sm"])
        info_col.setContentsMargins(0, 0, 0, 0)

        # Name + ID
        header = QVBoxLayout()
        header.setSpacing(2)
        self.name_label = QLabel()
        self.name_label.setWordWrap(True)
        self.id_label = QLabel()
        header.addWidget(self.name_label)
        header.addWidget(self.id_label)
        info_col.addLayout(header)

        info_col.addSpacing(SPACING["xs"])

        # Details grid: label / value pairs
        self.details_grid = QGridLayout()
        self.details_grid.setHorizontalSpacing(SPACING["md"])
        self.details_grid.setVerticalSpacing(SPACING["xs"])
        self.details_grid.setContentsMargins(0, 0, 0, 0)

        self.group_key_label = QLabel(t("card.group_label"))
        self.plan_key_label = QLabel(t("card.plan_label"))
        self.sessions_key_label = QLabel(t("card.sessions_label"))

        self.group_label = QLabel()
        self.plan_label = QLabel()
        self.sessions_label = QLabel()

        for lbl in (self.group_label, self.plan_label, self.sessions_label):
            lbl.setWordWrap(True)

        self.details_grid.addWidget(self.group_key_label, 0, 0)
        self.details_grid.addWidget(self.group_label,     0, 1)
        self.details_grid.addWidget(self.plan_key_label,  1, 0)
        self.details_grid.addWidget(self.plan_label,      1, 1)
        self.details_grid.addWidget(self.sessions_key_label, 2, 0)
        self.details_grid.addWidget(self.sessions_label,  2, 1)
        self.details_grid.setColumnStretch(1, 1)

        info_col.addLayout(self.details_grid)
        info_col.addStretch()

        # Status pill (hidden by default)
        pill_row = QHBoxLayout()
        self.status_label = Pill("", "success")
        self.status_label.setVisible(False)
        pill_row.addWidget(self.status_label)
        pill_row.addStretch()
        info_col.addLayout(pill_row)

        outer.addLayout(info_col, stretch=1)

    # ---------- theming ----------

    def restyle(self):
        tm = theme()

        self.setStyleSheet(
            f"QFrame#playerCard {{"
            f"  background-color: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['lg']}px;"
            f"}}"
        )

        # Photo — round-ish square with a soft surface
        self.photo_label.setStyleSheet(
            f"QLabel {{"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['md']}px;"
            f"  background-color: {tm.color('surface_alt')};"
            f"  color: {tm.color('text_secondary')};"
            f"  font-size: 40px;"
            f"  font-weight: 400;"
            f"}}"
        )

        # Name
        self.name_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['section']['size']}px;"
            f"  font-weight: 600;"
            f"}}"
        )

        # ID
        self.id_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['meta']['size']}px;"
            f"}}"
        )

        # Key labels (left column of grid)
        for lbl in (self.group_key_label, self.plan_key_label, self.sessions_key_label):
            lbl.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text_secondary')};"
                f"  background-color: transparent;"
                f"  font-size: {TYPOGRAPHY['body']['size']}px;"
                f"  font-weight: 600;"
                f"}}"
            )

        # Value labels (right column of grid)
        for lbl in (self.group_label, self.plan_label, self.sessions_label):
            lbl.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text')};"
                f"  background-color: transparent;"
                f"  font-size: {TYPOGRAPHY['body']['size']}px;"
                f"}}"
            )

    # ---------- photo ----------

    def set_photo(self, photo_path):
        if photo_path and os.path.exists(photo_path):
            pixmap = QPixmap(photo_path).scaled(
                PHOTO_SIZE, PHOTO_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.photo_label.setPixmap(pixmap)
        else:
            self.photo_label.setPixmap(QPixmap())
            self.photo_label.setText("👤")

    # ---------- public API ----------

    def display_player(self, player, subscription=None, check_in_state=None):
        self.set_photo(player.photo_path)
        self.name_label.setText(player.full_name)
        self.id_label.setText(f"ID: {player.player_id}")


        # Show ALL activities the player is currently enrolled in.
        try:
            from services import subscription_service, activity_service
            subs = subscription_service.get_all_active(player.player_id)
            activity_names = []
            for sub in subs:
                if sub.activity_id:
                    act = activity_service.get(sub.activity_id)
                    if act:
                        activity_names.append(activity_service.get_localized_name(act))
            self.group_label.setText(", ".join(activity_names) if activity_names else "—")
        except Exception:
            self.group_label.setText("—")

        if check_in_state == "checked_in":
            self.status_label.set_status(t("card.status.checked_in"), "success")
            self.status_label.setVisible(True)
        elif check_in_state == "denied":
            self.status_label.set_status(t("card.status.denied"), "danger")
            self.status_label.setVisible(True)
        else:
            self.status_label.setVisible(False)

    def clear(self):
        self.set_photo(None)
        self.name_label.setText("")
        self.id_label.setText("")
        self.group_label.setText("")
        self.plan_label.setText("")
        self.sessions_label.setText("")
        self.status_label.setVisible(False)