"""
Dialog for editing an existing subscription — v5 design (matches users_dialog v5).

Every field that can be changed after activation is editable here:
  - activity
  - sessions total (remaining adjusts by delta)
  - allowed days
  - start date (recomputes expiry)
  - payment amount + date (updates the linked ledger row)

Logs every change to the audit log. Uses services.subscription_service
for validation.

Design v5 changes:
  * Wider (560 px) to match SubscriptionFormDialog.
  * Required-field asterisks via _FieldLabel.
  * Field growth policy + divider + styled error banner.
  * WA_DontShowOnScreen flash guard during construction.
"""

from datetime import date

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPushButton,
    QCheckBox, QWidget, QGridLayout, QFrame,
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


class EditSubscriptionDialog(ThemedWidget, QDialog):
    """
    Opens with an existing Subscription row. Returns accepted() on
    successful save.
    """

    def __init__(self, subscription, parent=None):
        QDialog.__init__(self, parent)

        # Flash guard.
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)

        try:
            self._sub = subscription
            self.setWindowTitle(t("dlg.edit_sub.title"))
            self.setModal(True)
            self.setMinimumWidth(560)

            self._build_ui()
            self._prefill(subscription)
            self._init_theme()
        finally:
            self.setUpdatesEnabled(True)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
            self.update()

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
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # ---- Activity picker ----
        self.activity_combo = QComboBox(self)
        for act in activity_service.list_active():
            name = activity_service.get_localized_name(act)
            self.activity_combo.addItem(name, act.activity_id)

        # ---- Sessions total ----
        self.sessions_spin = QSpinBox(self)
        self.sessions_spin.setMinimum(1)
        self.sessions_spin.setMaximum(9999)

        # ---- Sessions remaining (read-only display) ----
        self.remaining_label = QLabel(self)

        # ---- Allowed days — checkbox grid ----
        days_container = QWidget(self)
        days_grid = QGridLayout(days_container)
        days_grid.setContentsMargins(0, 0, 0, 0)
        days_grid.setSpacing(SPACING["xs"])
        self.day_checkboxes = {}
        for i, (day_key, day_label_key) in enumerate(WEEKDAYS):
            cb = QCheckBox(t(day_label_key), self)
            self.day_checkboxes[day_key] = cb
            days_grid.addWidget(cb, i // 4, i % 4)

        # ---- Start date ----
        self.start_date = QDateEdit(self)
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")

        # ---- Payment amount ----
        self.payment_amount = QDoubleSpinBox(self)
        self.payment_amount.setMinimum(0)
        self.payment_amount.setMaximum(9999999)
        self.payment_amount.setDecimals(2)
        self.payment_amount.setPrefix("EGP ")

        # ---- Payment date ----
        self.payment_date = QDateEdit(self)
        self.payment_date.setCalendarPopup(True)
        self.payment_date.setDisplayFormat("yyyy-MM-dd")

        # ---- Expiry preview ----
        self.expiry_label = QLabel(self)
        self.expiry_label.setWordWrap(True)

        # ---- Assemble form with asterisks ----
        form.addRow(_FieldLabel(t("dlg.edit_sub.activity"), True, self), self.activity_combo)
        form.addRow(_FieldLabel(t("dlg.edit_sub.sessions"), True, self), self.sessions_spin)
        form.addRow(_FieldLabel(t("dlg.edit_sub.remaining_current"), False, self), self.remaining_label)
        form.addRow(_FieldLabel(t("dlg.edit_sub.days"), True, self), days_container)
        form.addRow(_FieldLabel(t("dlg.edit_sub.start_date"), True, self), self.start_date)
        form.addRow(_FieldLabel(t("dlg.edit_sub.payment"), True, self), self.payment_amount)
        form.addRow(_FieldLabel(t("dlg.edit_sub.payment_date"), True, self), self.payment_date)
        form.addRow(_FieldLabel(t("dlg.edit_sub.expiry_preview"), False, self), self.expiry_label)
        root.addLayout(form)

        # ---- Divider ----
        divider = QFrame(self)
        divider.setObjectName("editSubFormDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            f"QFrame#editSubFormDivider {{"
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
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACING["sm"])
        btn_row.setContentsMargins(0, SPACING["sm"], 0, 0)

        cancel_btn = QPushButton(t("dlg.edit_sub.cancel"), self)
        make_secondary(cancel_btn)
        cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton(t("dlg.edit_sub.save"), self)
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
        # Expiry preview becomes a soft pill like the create dialog's green one,
        # but neutral (surface_alt) since it's a preview, not a confirmation.
        self.expiry_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: {tm.color('surface_alt')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 4px 10px;"
            f"  font-size: 13px;"
            f"  font-weight: 600;"
            f"}}"
        )