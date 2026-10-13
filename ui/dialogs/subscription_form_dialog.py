"""Subscription activation dialog — v4 design."""

import os
import sys
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QDoubleSpinBox,
    QDateEdit, QPushButton, QHBoxLayout, QLabel,
)
from PyQt6.QtCore import QDate
from ui.message_box import ask
from services import audit_service
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import load_config, get_plan_label
from services import subscription_service
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


class SubscriptionFormDialog(ThemedWidget, QDialog):
    def __init__(self, player_id, activated_by="reception", parent=None):
        QDialog.__init__(self, parent)
        self.player_id = player_id
        self.activated_by = activated_by
        self.setWindowTitle(t("dlg.sub.title"))
        self.setMinimumWidth(400)
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])

        self.plan_input = QComboBox()
        config = load_config()
        for key, plan in config["plans"].items():
            days = ", ".join(plan["allowed_days"])
            self.plan_input.addItem(f"{get_plan_label(key)} ({days})", key)

        self.start_date_input = QDateEdit()
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDisplayFormat("yyyy-MM-dd")
        self.start_date_input.setDate(QDate.currentDate())
        self.start_date_input.dateChanged.connect(self._update_expiry_preview)

        self.payment_amount_input = QDoubleSpinBox()
        self.payment_amount_input.setMaximum(100000)
        self.payment_amount_input.setPrefix("EGP ")

        self.payment_date_input = QDateEdit()
        self.payment_date_input.setCalendarPopup(True)
        self.payment_date_input.setDisplayFormat("yyyy-MM-dd")
        self.payment_date_input.setDate(QDate.currentDate())
        self.payment_date_input.dateChanged.connect(self._update_expiry_preview)

        # Expiry preview — shown as a highlighted info chip
        self.expiry_label = QLabel()

        form.addRow(t("dlg.sub.plan"), self.plan_input)
        form.addRow(t("dlg.sub.start_date"), self.start_date_input)
        form.addRow(t("dlg.sub.expires_on"), self.expiry_label)
        form.addRow(t("dlg.sub.payment"), self.payment_amount_input)
        form.addRow(t("dlg.sub.payment_date"), self.payment_date_input)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        cancel_button = QPushButton(t("dlg.sub.cancel"))
        make_secondary(cancel_button)
        save_button = QPushButton(t("dlg.sub.activate"))
        save_button.setDefault(True)
        save_button.clicked.connect(self._on_save)
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

        self._update_expiry_preview()

    def restyle(self):
        tm = theme()
        self.expiry_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('success')};"
            f"  background-color: {tm.color('success_soft')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 4px 10px;"
            f"  font-weight: 600;"
            f"  font-size: 13px;"
            f"}}"
        )

    def _update_expiry_preview(self):
        qd = self.start_date_input.date()
        start = date(qd.year(), qd.month(), qd.day())
        pd = self.payment_date_input.date()
        payment_date = date(pd.year(), pd.month(), pd.day())
        expiry = subscription_service.compute_expiry_date(start, payment_date)
        self.expiry_label.setText(expiry.isoformat())

    def _on_save(self):
        plan_type = self.plan_input.currentData()
        qd = self.start_date_input.date()
        start = date(qd.year(), qd.month(), qd.day())
        pd = self.payment_date_input.date()
        payment_date = date(pd.year(), pd.month(), pd.day())
        amount = self.payment_amount_input.value()

        if amount <= 0:
            if not ask(self, t("dlg.sub.zero_title"), t("dlg.sub.zero_msg")):
                return


        self.new_subscription_id = subscription_service.activate(
            self.player_id, plan_type, start, self.activated_by, amount, payment_date,
        )

        audit_service.subscription_activated(
            subscription_id=self.new_subscription_id,
            player_id=self.player_id,
            plan_type=plan_type,
        )
        self.accept()