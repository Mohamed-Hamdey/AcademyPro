"""
Add / edit expense dialog — v5 design (matches users_dialog v5).

Header-style form, required-field asterisks, styled error banner,
flash guard during construction.
"""

import os
import sys
from datetime import date

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit,
    QDoubleSpinBox, QDateEdit, QPushButton, QHBoxLayout, QLabel,
    QWidget, QFrame,
)
from qtpy.QtCore import Qt, QDate

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import expense_service
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


class ExpenseFormDialog(ThemedWidget, QDialog):
    def __init__(self, expense=None, parent=None):
        QDialog.__init__(self, parent)

        # Flash guard.
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)

        try:
            self.editing = expense is not None
            self.expense = expense
            self.setWindowTitle(
                t("expenses.dialog.title_edit") if self.editing
                else t("expenses.dialog.title_add")
            )
            self.setMinimumWidth(520)

            self._build_ui()
            if expense:
                self._prefill(expense)
            self._init_theme()
        finally:
            self.setUpdatesEnabled(True)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
            self.update()

    # ---------- UI ----------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["md"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # ---- Fields ----
        self.category_input = QComboBox(self)
        for key in expense_service.CATEGORIES:
            self.category_input.addItem(t(f"expenses.cat.{key}"), key)

        self.description_input = QLineEdit(self)

        self.amount_input = QDoubleSpinBox(self)
        self.amount_input.setMaximum(1_000_000)
        self.amount_input.setPrefix("EGP ")
        self.amount_input.setDecimals(2)

        self.date_input = QDateEdit(self)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setDate(QDate.currentDate())

        # ---- Form rows with asterisks (all required) ----
        form.addRow(_FieldLabel(t("expenses.dialog.category"), True, self), self.category_input)
        form.addRow(_FieldLabel(t("expenses.dialog.description"), True, self), self.description_input)
        form.addRow(_FieldLabel(t("expenses.dialog.amount"), True, self), self.amount_input)
        form.addRow(_FieldLabel(t("expenses.dialog.date"), True, self), self.date_input)
        layout.addLayout(form)

        # ---- Divider ----
        divider = QFrame(self)
        divider.setObjectName("expenseFormDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            f"QFrame#expenseFormDivider {{"
            f"  background-color: {_col('divider', 'border', '#E8EDF3')};"
            f"  border: none;"
            f"}}"
        )
        layout.addWidget(divider)

        # ---- Error banner ----
        self.error_label = QLabel("", self)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # ---- Buttons ----
        buttons = QHBoxLayout()
        buttons.setSpacing(SPACING["sm"])
        buttons.setContentsMargins(0, SPACING["sm"], 0, 0)

        cancel = QPushButton(t("expenses.dialog.cancel"), self)
        make_secondary(cancel)

        save = QPushButton(t("expenses.dialog.save"), self)
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        cancel.clicked.connect(self.reject)

        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    # ---------- theming ----------

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

    # ---------- prefill ----------

    def _prefill(self, e):
        idx = self.category_input.findData(e.category)
        if idx >= 0:
            self.category_input.setCurrentIndex(idx)
        self.description_input.setText(e.description)
        self.amount_input.setValue(e.amount)
        try:
            y, m, d = (int(x) for x in e.expense_date.split("-"))
            self.date_input.setDate(QDate(y, m, d))
        except Exception:
            pass

    # ---------- save ----------

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()

    def _on_save(self):
        self.error_label.hide()

        category = self.category_input.currentData()
        description = self.description_input.text().strip()
        amount = self.amount_input.value()
        qd = self.date_input.date()
        exp_date = date(qd.year(), qd.month(), qd.day())

        try:
            if self.editing:
                expense_service.update(
                    self.expense.expense_id, category, description,
                    amount, exp_date,
                )
            else:
                expense_service.create(category, description, amount, exp_date)
        except Exception as e:
            self._show_error(str(e))
            return

        # Audit
        try:
            from services import audit_service
            audit_service.record(
                "expense.create" if not self.editing else "expense.update",
                target_type="expense",
                details={"category": category, "amount": amount},
            )
        except Exception:
            pass

        self.accept()