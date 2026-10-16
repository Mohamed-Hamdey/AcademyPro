"""
Add / edit expense dialog — v4 design.
"""

import os
import sys
from datetime import date

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit,
    QDoubleSpinBox, QDateEdit, QPushButton, QHBoxLayout, QLabel,
)
from qtpy.QtCore import QDate

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import expense_service
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


class ExpenseFormDialog(ThemedWidget, QDialog):
    def __init__(self, expense=None, parent=None):
        QDialog.__init__(self, parent)
        self.editing = expense is not None
        self.expense = expense
        self.setWindowTitle(
            t("expenses.dialog.title_edit") if self.editing
            else t("expenses.dialog.title_add")
        )
        self.setMinimumWidth(420)
        self._build_ui()
        if expense:
            self._prefill(expense)
        self._init_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"],
                                  SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])

        self.category_input = QComboBox()
        for key in expense_service.CATEGORIES:
            self.category_input.addItem(t(f"expenses.cat.{key}"), key)

        self.description_input = QLineEdit()

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setMaximum(1_000_000)
        self.amount_input.setPrefix("EGP ")
        self.amount_input.setDecimals(2)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setDate(QDate.currentDate())

        form.addRow(t("expenses.dialog.category"), self.category_input)
        form.addRow(t("expenses.dialog.description"), self.description_input)
        form.addRow(t("expenses.dialog.amount"), self.amount_input)
        form.addRow(t("expenses.dialog.date"), self.date_input)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACING["sm"])
        cancel = QPushButton(t("expenses.dialog.cancel"))
        make_secondary(cancel)
        save = QPushButton(t("expenses.dialog.save"))
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        cancel.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

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

    def _prefill(self, e):
        idx = self.category_input.findData(e.category)
        if idx >= 0:
            self.category_input.setCurrentIndex(idx)
        self.description_input.setText(e.description)
        self.amount_input.setValue(e.amount)
        y, m, d = (int(x) for x in e.expense_date.split("-"))
        self.date_input.setDate(QDate(y, m, d))

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
        