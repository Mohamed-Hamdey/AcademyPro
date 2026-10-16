"""
Activity picker dialog — v4 design.

Shown when a player has 2+ subscriptions valid today and the receptionist
needs to pick which class they're attending.

Each row shows:
  - Activity name (localized)
  - Package label (preset or "Custom")
  - Sessions remaining / total
  - Training days

The receptionist clicks a row to select it, then Confirm.
Or clicks Cancel to abort the check-in entirely (nothing gets logged).
"""

import os
import sys

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem,
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_plan_label
from services import activity_service
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


class ActivityPickerDialog(ThemedWidget, QDialog):
    """
    Modal picker. After exec():
      dialog.chosen_subscription_id  → int, or None if cancelled
    """

    def __init__(self, player_name: str, subscriptions: list, parent=None):
        QDialog.__init__(self, parent)
        self.player_name = player_name
        self.subscriptions = subscriptions
        self.chosen_subscription_id = None

        self.setWindowTitle(t("checkin.picker.title"))
        self.setModal(True)
        self.setMinimumWidth(480)

        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        # Header
        self.header_label = QLabel(
            t("checkin.picker.header", name=self.player_name)
        )
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        # List of subscriptions to choose from
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(180)
        self.list_widget.itemDoubleClicked.connect(self._on_confirm)

        for sub in self.subscriptions:
            act = activity_service.get(sub.activity_id) if sub.activity_id else None
            act_name = activity_service.get_localized_name(act) if act else "—"

            if sub.plan_type:
                plan_label = get_plan_label(sub.plan_type)
            else:
                plan_label = t("detail.sub.custom")

            sessions = f"{sub.sessions_remaining} / {sub.sessions_total}"
            days = ", ".join(t(f"weekday.{d.lower()}") for d in (sub.allowed_days or []))

            text = f"{act_name}   ·   {plan_label}   ·   {sessions}\n{days}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, sub.subscription_id)
            item.setSizeHint(item.sizeHint().expandedTo(item.sizeHint()))
            self.list_widget.addItem(item)

        self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget)

        # Buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        self.cancel_button = QPushButton(t("checkin.picker.cancel"))
        make_secondary(self.cancel_button)
        self.confirm_button = QPushButton(t("checkin.picker.confirm"))
        self.confirm_button.setDefault(True)
        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button.clicked.connect(self._on_confirm)
        button_row.addStretch()
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.confirm_button)
        layout.addLayout(button_row)

    def restyle(self):
        tm = theme()
        self.header_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 15px;"
            f"  font-weight: 600;"
            f"}}"
        )
        self.list_widget.setStyleSheet(
            f"QListWidget {{"
            f"  background-color: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['md']}px;"
            f"  padding: 6px;"
            f"  outline: none;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 12px 14px;"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  color: {tm.color('text')};"
            f"  margin: 2px;"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background-color: {tm.color('primary_soft')};"
            f"  color: {tm.color('text')};"
            f"}}"
        )

    def _on_confirm(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.chosen_subscription_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()