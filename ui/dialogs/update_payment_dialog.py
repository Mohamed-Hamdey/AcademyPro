"""
Update payment dialog — v5 design (matches users_dialog v5).

Small focused dialog: intro banner → divider → amount + date → buttons.

Design v5 polish:
  * Wider (460 px).
  * Required-field asterisks via _FieldLabel.
  * Intro banner in surface_alt with rounded corners.
  * Divider between the form and the buttons.
  * WA_DontShowOnScreen flash guard during construction.
"""

from datetime import date

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox, QDateEdit,
    QPushButton, QHBoxLayout, QLabel, QWidget, QFrame,
)
from qtpy.QtCore import Qt, QDate

from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


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


class UpdatePaymentDialog(ThemedWidget, QDialog):
    def __init__(self, current_amount=0.0, parent=None):
        QDialog.__init__(self, parent)

        # Flash guard.
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)

        try:
            self.setWindowTitle(t("dlg.payment.title"))
            self.setMinimumWidth(460)
            self._build_ui(current_amount)
            self._init_theme()
        finally:
            self.setUpdatesEnabled(True)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
            self.update()

    # ---------- UI ----------

    def _build_ui(self, current_amount):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["md"])

        # ---- Intro banner ----
        self.intro = QLabel(t("dlg.payment.intro"), self)
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)

        # ---- Divider ----
        layout.addWidget(self._make_hr("paymentFormDividerTop"))

        # ---- Form ----
        form = QFormLayout()
        form.setSpacing(SPACING["sm"])
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.amount_input = QDoubleSpinBox(self)
        self.amount_input.setMaximum(100000)
        self.amount_input.setPrefix("EGP ")
        self.amount_input.setValue(current_amount or 0.0)

        self.date_input = QDateEdit(self)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setDate(QDate.currentDate())

        form.addRow(_FieldLabel(t("dlg.payment.amount"), True, self), self.amount_input)
        form.addRow(_FieldLabel(t("dlg.payment.date"), True, self), self.date_input)
        layout.addLayout(form)

        # ---- Divider ----
        layout.addWidget(self._make_hr("paymentFormDividerBottom"))

        # ---- Buttons ----
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        button_row.setContentsMargins(0, SPACING["sm"], 0, 0)

        cancel_button = QPushButton(t("dlg.payment.cancel"), self)
        make_secondary(cancel_button)

        save_button = QPushButton(t("dlg.payment.save"), self)
        save_button.setDefault(True)
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    def _make_hr(self, object_name: str) -> QFrame:
        line = QFrame(self)
        line.setObjectName(object_name)
        line.setFixedHeight(1)
        return line

    # ---------- theming ----------

    def restyle(self):
        tm = theme()

        # Intro banner — soft "info" block, matching the restore_backup
        # and privacy_consent hint banners.
        self.intro.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: {tm.color('surface_alt')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 10px 14px;"
            f"  font-size: 12px;"
            f"}}"
        )

        # Dividers
        for name in ("paymentFormDividerTop", "paymentFormDividerBottom"):
            for line in self.findChildren(QFrame, name):
                line.setStyleSheet(
                    f"QFrame#{name} {{"
                    f"  background-color: {tm.color('divider')};"
                    f"  border: none;"
                    f"}}"
                )

    # ---------- result ----------

    def get_values(self):
        qd = self.date_input.date()
        return self.amount_input.value(), date(qd.year(), qd.month(), qd.day())