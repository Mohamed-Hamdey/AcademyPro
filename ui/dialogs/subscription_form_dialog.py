"""
Subscription activation dialog — v4 with activities and flexible sessions.

Fields:
  * Activity picker (dropdown of active activities)
  * Preset dropdown (optional: 4, 8, 12 sessions, or "Custom")
  * Sessions count (spinbox; disabled when a preset is chosen, editable on Custom)
  * Training days (multi-select checkboxes; prefilled from the activity's
    default_days but freely editable per player)
  * Start date, expiry preview
  * Payment amount + payment date

When the user picks a preset, the sessions spinbox is set to the preset's
value and disabled. Picking "Custom" enables it.
"""

import os
import sys
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QDoubleSpinBox,
    QDateEdit, QPushButton, QHBoxLayout, QLabel, QSpinBox, QCheckBox,
    QWidget, QGridLayout,
)
from PyQt6.QtCore import QDate
from ui.message_box import ask

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import load_config, get_plan_label
from services import subscription_service, activity_service
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


WEEKDAYS = [
    ("Monday",    "weekday.monday"),
    ("Tuesday",   "weekday.tuesday"),
    ("Wednesday", "weekday.wednesday"),
    ("Thursday",  "weekday.thursday"),
    ("Friday",    "weekday.friday"),
    ("Saturday",  "weekday.saturday"),
    ("Sunday",    "weekday.sunday"),
]

CUSTOM_PRESET = "__custom__"


class SubscriptionFormDialog(ThemedWidget, QDialog):
    def __init__(self, player_id, activated_by="reception", parent=None):
        QDialog.__init__(self, parent)
        self.player_id = player_id
        self.activated_by = activated_by
        self.setWindowTitle(t("dlg.sub.title"))
        self.setMinimumWidth(480)
        self._build_ui()
        self._init_theme()

    # ---------- UI ----------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])

        # ---- Activity picker ----
        self.activity_input = QComboBox()
        self._activities = activity_service.list_active()
        for a in self._activities:
            label = activity_service.get_localized_name(a)
            # Include both names, in case the receptionist sees someone who
            # doesn't know the app's language
            display = f"{a.name_en} · {a.name_ar}" if a.name_en != a.name_ar else a.name_en
            self.activity_input.addItem(display, a.activity_id)
        self.activity_input.currentIndexChanged.connect(self._on_activity_changed)

        # ---- Preset dropdown ----
        self.preset_input = QComboBox()
        config = load_config()
        for key, plan in config.get("plans", {}).items():
            self.preset_input.addItem(
                f"{get_plan_label(key)} ({plan['sessions_total']})", key
            )
        self.preset_input.addItem(t("dlg.sub.preset_custom"), CUSTOM_PRESET)
        # Default to the first preset
        self.preset_input.currentIndexChanged.connect(self._on_preset_changed)

        # ---- Sessions count ----
        self.sessions_input = QSpinBox()
        self.sessions_input.setRange(1, 999)
        self.sessions_input.setValue(8)

        # ---- Training days ----
        days_container = QWidget()
        days_grid = QGridLayout(days_container)
        days_grid.setContentsMargins(0, 0, 0, 0)
        days_grid.setSpacing(SPACING["xs"])
        self.day_checkboxes = {}
        for i, (day_key, day_label_key) in enumerate(WEEKDAYS):
            cb = QCheckBox(t(day_label_key))
            self.day_checkboxes[day_key] = cb
            days_grid.addWidget(cb, i // 4, i % 4)

        # ---- Dates + payment ----
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

        self.expiry_label = QLabel()

        form.addRow(t("dlg.sub.activity"), self.activity_input)
        form.addRow(t("dlg.sub.preset"), self.preset_input)
        form.addRow(t("dlg.sub.sessions"), self.sessions_input)
        form.addRow(t("dlg.sub.days"), days_container)
        form.addRow(t("dlg.sub.start_date"), self.start_date_input)
        form.addRow(t("dlg.sub.expires_on"), self.expiry_label)
        form.addRow(t("dlg.sub.payment"), self.payment_amount_input)
        form.addRow(t("dlg.sub.payment_date"), self.payment_date_input)
        layout.addLayout(form)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Buttons
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

        # Initialize the state
        self._on_activity_changed()
        self._on_preset_changed()
        self._update_expiry_preview()

    # ---------- theming ----------

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
        self.error_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('danger')};"
            f"  background-color: {tm.color('danger_soft')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 8px 12px;"
            f"}}"
        )

    # ---------- state handlers ----------

    def _current_activity(self):
        idx = self.activity_input.currentIndex()
        if idx < 0 or idx >= len(self._activities):
            return None
        return self._activities[idx]

    def _on_activity_changed(self):
        """When activity changes, reset the training days to its defaults."""
        activity = self._current_activity()
        if activity is None:
            return
        # Clear all, then check the ones in the activity's default_days
        for day_key, cb in self.day_checkboxes.items():
            cb.setChecked(day_key in activity.default_days)

    def _on_preset_changed(self):
        """When preset changes, if it's a real preset fill the spinbox and
        disable it; if it's Custom, enable the spinbox."""
        preset_key = self.preset_input.currentData()
        if preset_key == CUSTOM_PRESET:
            self.sessions_input.setEnabled(True)
        else:
            config = load_config()
            plan = config.get("plans", {}).get(preset_key, {})
            self.sessions_input.setValue(int(plan.get("sessions_total", 8)))
            self.sessions_input.setEnabled(False)

    def _update_expiry_preview(self):
        qd = self.start_date_input.date()
        start = date(qd.year(), qd.month(), qd.day())
        pd = self.payment_date_input.date()
        payment_date = date(pd.year(), pd.month(), pd.day())
        expiry = subscription_service.compute_expiry_date(start, payment_date)
        self.expiry_label.setText(expiry.isoformat())

    # ---------- save ----------

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()

    def _on_save(self):
        self.error_label.hide()

        activity = self._current_activity()
        if activity is None:
            self._show_error(t("dlg.sub.error.no_activity"))
            return

        sessions = self.sessions_input.value()
        if sessions <= 0:
            self._show_error(t("dlg.sub.error.invalid_sessions"))
            return

        days = [day for day, cb in self.day_checkboxes.items() if cb.isChecked()]
        if not days:
            self._show_error(t("dlg.sub.error.no_days"))
            return

        preset_key = self.preset_input.currentData()
        plan_type = None if preset_key == CUSTOM_PRESET else preset_key

        qd = self.start_date_input.date()
        start = date(qd.year(), qd.month(), qd.day())
        pd = self.payment_date_input.date()
        payment_date = date(pd.year(), pd.month(), pd.day())
        amount = self.payment_amount_input.value()

        if amount <= 0:
            if not ask(self, t("dlg.sub.zero_title"), t("dlg.sub.zero_msg")):
                return

        try:
            self.new_subscription_id = subscription_service.activate(
                player_id=self.player_id,
                activity_id=activity.activity_id,
                sessions_total=sessions,
                allowed_days=days,
                start_date=start,
                activated_by=self.activated_by,
                payment_amount=amount,
                payment_date=payment_date,
                plan_type=plan_type,
            )
        except ValueError as e:
            self._show_error(str(e))
            return
        except Exception as e:
            self._show_error(str(e))
            return

        # Audit
        try:
            from services import audit_service
            audit_service.subscription_activated(
                subscription_id=self.new_subscription_id,
                player_id=self.player_id,
                plan_type=plan_type or "custom",
            )
        except Exception:
            pass

        self.accept()