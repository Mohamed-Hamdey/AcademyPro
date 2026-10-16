"""Deny popup — v4 design."""

import os
import sys

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame,
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ui.message_box import warn
from ui.theme import theme, ThemedWidget, make_danger, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


class DenyPopup(ThemedWidget, QDialog):
    def __init__(self, player_name, reason, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(t("dlg.deny.title"))
        self.setModal(True)
        self.setMinimumWidth(420)

        self._override_confirmed = False
        self._override_note = ""

        self._build_ui(player_name, reason)
        self._init_theme()

    def _build_ui(self, player_name, reason):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        self.name_label = QLabel(player_name)
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        # Reason box
        reason_box = QFrame()
        reason_box.setObjectName("reasonBox")
        rl = QVBoxLayout(reason_box)
        rl.setContentsMargins(SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"])
        self.reason_label = QLabel(t("dlg.deny.reason_prefix", reason=reason))
        self.reason_label.setWordWrap(True)
        rl.addWidget(self.reason_label)
        self.reason_box = reason_box
        layout.addWidget(reason_box)

        # Override note
        self.note_hint = QLabel(t("dlg.deny.note_hint"))
        layout.addWidget(self.note_hint)

        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText(t("dlg.deny.note_placeholder"))
        layout.addWidget(self.note_input)

        # Buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        self.dismiss_button = QPushButton(t("dlg.deny.dismiss"))
        make_secondary(self.dismiss_button)
        self.override_button = QPushButton(t("dlg.deny.override"))
        make_danger(self.override_button)

        button_row.addStretch()
        button_row.addWidget(self.dismiss_button)
        button_row.addWidget(self.override_button)
        layout.addLayout(button_row)

        self.override_button.clicked.connect(self._on_override_clicked)
        self.dismiss_button.clicked.connect(self.reject)

    def restyle(self):
        tm = theme()
        self.name_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 18px;"
            f"  font-weight: 700;"
            f"}}"
        )
        self.reason_box.setStyleSheet(
            f"QFrame#reasonBox {{"
            f"  background-color: {tm.color('danger_soft')};"
            f"  border: 1px solid {tm.color('danger')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"}}"
        )
        self.reason_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('danger')};"
            f"  background-color: transparent;"
            f"  font-size: 14px;"
            f"  font-weight: 600;"
            f"}}"
        )
        self.note_hint.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"}}"
        )

    def _on_override_clicked(self):
        note = self.note_input.text().strip()
        if not note:
            warn(
                self, t("dlg.deny.note_required_title"),
                t("dlg.deny.note_required_msg"),
            )
            return
        self._override_note = note
        self._override_confirmed = True
        self.accept()

    def result_data(self):
        return self._override_confirmed, (self._override_note or None)