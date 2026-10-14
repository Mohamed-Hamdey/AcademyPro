"""
Player card widget — v4 design.

Used in two places:
  * Scan result (after a check-in) — includes a check-in status pill
  * Player detail overview — includes a subscription status pill

Public API is unchanged:
    card.display_player(player, subscription, check_in_state, display=None)
    card.clear()
    card.set_photo(path_or_None)

`display` is an optional dict from
`subscription_service.get_display_status(player_id)` — when passed,
the card shows the subscription status pill on the detail screen.
"""

import os
import sys

from PyQt6.QtWidgets import (
    QHBoxLayout, QGridLayout, QLabel, QFrame,
)
from PyQt6.QtGui import QPixmap, QColor, QPainter, QBrush
from PyQt6.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_plan_label
from ui.components import Pill
from ui.theme import theme, ThemedWidget
from ui.design import SPACING, RADIUS, TYPOGRAPHY
from ui.i18n import t


PHOTO_SIZE = 120
PHOTO_SMALL = 72


class PlayerCardWidget(QFrame, ThemedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playerCard")
        self._photo_is_custom = False
        self._initial_letter = ""
        self._build_ui()
        self._init_theme()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

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
        self.photo_label.setText("👤")
        outer.addWidget(self.photo_label, alignment=Qt.AlignmentFlag.AlignTop)

        # ---- Info column ----
        info_col = QGridLayout()
        info_col.setHorizontalSpacing(SPACING["md"])
        info_col.setVerticalSpacing(SPACING["xs"])
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setColumnStretch(1, 1)

        # Row 0: name (spans both columns)
        self.name_label = QLabel()
        self.name_label.setWordWrap(True)
        info_col.addWidget(self.name_label, 0, 0, 1, 2)

        # Row 1: id
        self.id_label = QLabel()
        info_col.addWidget(self.id_label, 1, 0, 1, 2)

        # Spacer row
        info_col.setRowMinimumHeight(2, SPACING["sm"])

        # Detail rows: key / value
        self.activities_key_label = QLabel(t("card.activities_label"))
        self.plan_key_label       = QLabel(t("card.plan_label"))
        self.sessions_key_label   = QLabel(t("card.sessions_label"))
        self.phone_key_label      = QLabel(t("card.phone_label"))
        self.nid_key_label        = QLabel(t("card.national_id_label"))

        self.activities_label = QLabel()
        self.plan_label       = QLabel()
        self.sessions_label   = QLabel()
        self.phone_label      = QLabel()
        self.nid_label        = QLabel()

        for lbl in (self.activities_label, self.plan_label, self.sessions_label,
                    self.phone_label, self.nid_label):
            lbl.setWordWrap(True)

        rows = [
            (self.activities_key_label, self.activities_label),
            (self.plan_key_label,       self.plan_label),
            (self.sessions_key_label,   self.sessions_label),
            (self.phone_key_label,      self.phone_label),
            (self.nid_key_label,        self.nid_label),
        ]
        for i, (k, v) in enumerate(rows):
            info_col.addWidget(k, i + 3, 0)
            info_col.addWidget(v, i + 3, 1)

        # Status pill row (below everything, aligned left)
        self.status_label = Pill("", "success")
        self.status_label.setVisible(False)
        pill_row = 3 + len(rows)
        info_col.addWidget(self.status_label, pill_row, 0, 1, 2,
                           alignment=Qt.AlignmentFlag.AlignLeft)

        outer.addLayout(info_col, stretch=1)

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

    def restyle(self):
        tm = theme()

        self.setStyleSheet(
            f"QFrame#playerCard {{"
            f"  background-color: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['lg']}px;"
            f"}}"
        )

        # Photo style depends on whether it's a custom image or the
        # fallback initial-circle.
        if self._photo_is_custom:
            self.photo_label.setStyleSheet(
                f"QLabel {{"
                f"  border: 1px solid {tm.color('border')};"
                f"  border-radius: {RADIUS['md']}px;"
                f"  background-color: {tm.color('surface_alt')};"
                f"}}"
            )
        else:
            self.photo_label.setStyleSheet(
                f"QLabel {{"
                f"  border: none;"
                f"  border-radius: {PHOTO_SMALL // 2}px;"
                f"  background-color: {tm.color('primary_soft')};"
                f"  color: {tm.color('primary')};"
                f"  font-size: 28px;"
                f"  font-weight: 700;"
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

        # Key labels
        for lbl in (self.activities_key_label, self.plan_key_label,
                    self.sessions_key_label, self.phone_key_label,
                    self.nid_key_label):
            lbl.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text_secondary')};"
                f"  background-color: transparent;"
                f"  font-size: {TYPOGRAPHY['body']['size']}px;"
                f"  font-weight: 600;"
                f"}}"
            )

        # Value labels
        for lbl in (self.activities_label, self.plan_label, self.sessions_label,
                    self.phone_label, self.nid_label):
            lbl.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text')};"
                f"  background-color: transparent;"
                f"  font-size: {TYPOGRAPHY['body']['size']}px;"
                f"}}"
            )

    # ------------------------------------------------------------------
    # Photo
    # ------------------------------------------------------------------

    def set_photo(self, photo_path, letter: str = ""):
        """
        If `photo_path` exists and is a valid file, show it.
        Otherwise show a circle with `letter` (defaults to "👤" if empty).
        """
        if photo_path and os.path.exists(photo_path):
            self._photo_is_custom = True
            self._initial_letter = ""
            self.photo_label.setFixedSize(PHOTO_SIZE, PHOTO_SIZE)
            pixmap = QPixmap(photo_path).scaled(
                PHOTO_SIZE, PHOTO_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.photo_label.setPixmap(pixmap)
        else:
            self._photo_is_custom = False
            self._initial_letter = (letter or "").strip()[:1].upper()
            self.photo_label.setFixedSize(PHOTO_SMALL, PHOTO_SMALL)
            self.photo_label.setPixmap(QPixmap())
            self.photo_label.setText(self._initial_letter or "👤")
        # Re-apply styles for the new mode
        self.restyle()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def display_player(self, player, subscription=None, check_in_state=None,
                       display=None):
        """
        player            : models.player.Player
        subscription      : most-recent active Subscription or None
        check_in_state    : "checked_in" | "denied" | None
        display           : optional dict from
                            subscription_service.get_display_status(player_id).
                            When provided and no check_in_state is given,
                            the card shows the subscription status pill.
        """
        # Photo / fallback
        self.set_photo(player.photo_path, letter=player.full_name or "")

        # Identity
        self.name_label.setText(player.full_name or "")
        self.id_label.setText(f"ID: {player.player_id}")

        # Activities — all currently active ones for this player
        try:
            from services import subscription_service, activity_service
            subs = subscription_service.get_all_active(player.player_id)
            names = []
            for s in subs:
                if s.activity_id:
                    act = activity_service.get(s.activity_id)
                    if act:
                        names.append(activity_service.get_localized_name(act))
            self.activities_label.setText(
                ", ".join(names) if names else t("card.no_data")
            )
        except Exception:
            self.activities_label.setText(t("card.no_data"))

        # Plan + sessions — from the most-recent subscription
        if subscription is not None:
            if subscription.plan_type:
                plan_text = get_plan_label(subscription.plan_type)
            else:
                plan_text = t("detail.sub.custom")
            self.plan_label.setText(plan_text)
            self.sessions_label.setText(t(
                "card.sessions_value",
                remaining=subscription.sessions_remaining,
                total=subscription.sessions_total,
            ))
        else:
            self.plan_label.setText(t("card.no_data"))
            self.sessions_label.setText(t("card.no_data"))

        # Contact
        self.phone_label.setText(player.phone or t("card.no_data"))
        self.nid_label.setText(player.national_id or t("card.no_data"))

        # Status pill
        if check_in_state == "checked_in":
            self.status_label.set_status(t("card.status.checked_in"), "success")
            self.status_label.setVisible(True)
        elif check_in_state == "denied":
            self.status_label.set_status(t("card.status.denied"), "danger")
            self.status_label.setVisible(True)
        elif display is not None:
            status = display.get("status", "none")
            key = {
                "active":    "players.status.active",
                "expired":   "players.status.expired",
                "suspended": "players.status.suspended",
                "none":      "players.status.none",
            }.get(status, "players.status.none")
            pill_kind = {
                "active":    "success",
                "expired":   "danger",
                "suspended": "warning",
                "none":      "neutral",
            }.get(status, "neutral")
            self.status_label.set_status(t(key), pill_kind)
            self.status_label.setVisible(True)
        else:
            self.status_label.setVisible(False)

    def clear(self):
        self.set_photo(None)
        self.name_label.setText("")
        self.id_label.setText("")
        self.activities_label.setText("")
        self.plan_label.setText("")
        self.sessions_label.setText("")
        self.phone_label.setText("")
        self.nid_label.setText("")
        self.status_label.setVisible(False)