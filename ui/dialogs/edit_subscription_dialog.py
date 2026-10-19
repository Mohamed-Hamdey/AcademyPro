"""
Dialog for editing an existing subscription.

Every field that can be changed after activation is editable here:
  - activity
  - sessions total (remaining adjusts by delta)
  - allowed days
  - start date (recomputes expiry)
  - payment amount + date (updates the linked ledger row)

Logs every change to the audit log. Uses services.subscription_service
for validation.
"""

from datetime import date

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPushButton,
    QCheckBox, QWidget, QGridLayout,
)
from qtpy.QtCore import Qt, QDate

from repositories import subscriptions_repo
from services import subscription_service, activity_service
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.message_box import info, warn


WEEKDAYS = [
    ("Monday",    "weekday.monday"),
    ("Tuesday",   "weekday.tuesday"),
    ("Wednesday", "weekday.wednesday"),
    ("Thursday",  "weekday.thursday"),
    ("Friday",    "weekday.friday"),
    ("Saturday",  "weekday.saturday"),
    ("Sunday",    "weekday.sunday"),
]


class EditSubscriptionDialog(ThemedWidget, QDialog):
    """
    Opens with an existing Subscription row. Returns accepted() on
    successful save.
    """

    def __init__(self, subscription, parent=None):
        QDialog.__init__(self, parent)
        self._sub = subscription
        self.setWindowTitle(t("dlg.edit_sub.title"))
        self.setModal(True)
        self.setMinimumWidth(480)

        self._build_ui()
        self._prefill(subscription)
        self._init_theme()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])

        # Activity picker
        self.activity_combo = QComboBox()
        for act in activity_service.list_active():
            name = activity_service.get_localized_name(act)
            self.activity_combo.addItem(name, act.activity_id)

        # Sessions total
        self.sessions_spin = QSpinBox()
        self.sessions_spin.setMinimum(1)
        self.sessions_spin.setMaximum(9999)

        # Sessions remaining (read-only display — updates based on delta)
        self.remaining_label = QLabel()

        # Allowed days — checkbox grid
        days_container = QWidget()
        days_grid = QGridLayout(days_container)
        days_grid.setContentsMargins(0, 0, 0, 0)
        days_grid.setSpacing(SPACING["xs"])
        self.day_checkboxes = {}
        for i, (day_key, day_label_key) in enumerate(WEEKDAYS):
            cb = QCheckBox(t(day_label_key))
            self.day_checkboxes[day_key] = cb
            days_grid.addWidget(cb, i // 4, i % 4)

        # Start date
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")

        # Payment amount
        self.payment_amount = QDoubleSpinBox()
        self.payment_amount.setMinimum(0)
        self.payment_amount.setMaximum(9999999)
        self.payment_amount.setDecimals(2)

        # Payment date
        self.payment_date = QDateEdit()
        self.payment_date.setCalendarPopup(True)
        self.payment_date.setDisplayFormat("yyyy-MM-dd")

        # Expiry preview (read-only)
        self.expiry_label = QLabel()
        self.expiry_label.setWordWrap(True)

        form.addRow(t("dlg.edit_sub.activity"), self.activity_combo)
        form.addRow(t("dlg.edit_sub.sessions"), self.sessions_spin)
        form.addRow(t("dlg.edit_sub.remaining_current"), self.remaining_label)
        form.addRow(t("dlg.edit_sub.days"), days_container)
        form.addRow(t("dlg.edit_sub.start_date"), self.start_date)
        form.addRow(t("dlg.edit_sub.payment"), self.payment_amount)
        form.addRow(t("dlg.edit_sub.payment_date"), self.payment_date)
        form.addRow(t("dlg.edit_sub.expiry_preview"), self.expiry_label)

        root.addLayout(form)

        # Error label (hidden)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACING["sm"])

        cancel_btn = QPushButton(t("dlg.edit_sub.cancel"))
        make_secondary(cancel_btn)
        cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton(t("dlg.edit_sub.save"))
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)

        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        root.addLayout(btn_row)

        # Live update for the expiry preview + remaining delta
        self.sessions_spin.valueChanged.connect(self._refresh_preview)
        self.start_date.dateChanged.connect(self._refresh_preview)
        self.payment_date.dateChanged.connect(self._refresh_preview)

    def _prefill(self, sub):
        # Activity
        for i in range(self.activity_combo.count()):
            if self.activity_combo.itemData(i) == sub.activity_id:
                self.activity_combo.setCurrentIndex(i)
                break

        # Sessions
        self.sessions_spin.setValue(sub.sessions_total)

        # Days
        for day_key in (sub.allowed_days or []):
            cb = self.day_checkboxes.get(day_key)
            if cb:
                cb.setChecked(True)

        # Dates
        try:
            y, m, d = map(int, sub.start_date.split("-"))
            self.start_date.setDate(QDate(y, m, d))
        except Exception:
            self.start_date.setDate(QDate.currentDate())

        if sub.payment_date:
            try:
                y, m, d = map(int, sub.payment_date.split("-"))
                self.payment_date.setDate(QDate(y, m, d))
            except Exception:
                self.payment_date.setDate(QDate.currentDate())
        else:
            self.payment_date.setDate(QDate.currentDate())

        # Amount
        self.payment_amount.setValue(float(sub.payment_amount or 0.0))

        self._refresh_preview()

    def _refresh_preview(self):
        # Sessions delta
        delta = self.sessions_spin.value() - self._sub.sessions_total
        new_remaining = max(0, self._sub.sessions_remaining + delta)
        self.remaining_label.setText(
            t("dlg.edit_sub.remaining_value",
              remaining=new_remaining, delta=f"{delta:+d}")
        )

        # Expiry preview
        try:
            sd = self.start_date.date()
            pd = self.payment_date.date()
            start = date(sd.year(), sd.month(), sd.day())
            pay = date(pd.year(), pd.month(), pd.day())
            expiry = subscription_service.compute_expiry_date(start, pay)
            self.expiry_label.setText(expiry.isoformat())
        except Exception:
            self.expiry_label.setText("—")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self):
        self.error_label.hide()

        activity_id = self.activity_combo.currentData()
        if activity_id is None:
            self._show_error(t("dlg.edit_sub.error.no_activity"))
            return

        sessions_total = self.sessions_spin.value()
        if sessions_total <= 0:
            self._show_error(t("dlg.edit_sub.error.invalid_sessions"))
            return

        days = [k for k, cb in self.day_checkboxes.items() if cb.isChecked()]
        if not days:
            self._show_error(t("dlg.edit_sub.error.no_days"))
            return

        sd = self.start_date.date()
        pd = self.payment_date.date()
        start_date = date(sd.year(), sd.month(), sd.day())
        payment_date = date(pd.year(), pd.month(), pd.day())

        payment_amount = float(self.payment_amount.value())

        try:
            subscription_service.update(
                self._sub.subscription_id,
                activity_id=activity_id,
                sessions_total=sessions_total,
                allowed_days=days,
                start_date=start_date,
                payment_amount=payment_amount,
                payment_date=payment_date,
            )
        except ValueError as e:
            self._show_error(str(e))
            return
        except Exception as e:
            self._show_error(str(e))
            return

        self.accept()

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

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
        self.remaining_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
        )
        self.expiry_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 13px;"
            f"  font-weight: 600;"
            f"}}"
        )