"""Update payment dialog — v4 design."""

from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox, QDateEdit,
    QPushButton, QHBoxLayout, QLabel,
)
from PyQt6.QtCore import QDate

from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING
from ui.i18n import t


class UpdatePaymentDialog(ThemedWidget, QDialog):
    def __init__(self, current_amount=0.0, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(t("dlg.payment.title"))
        self.setMinimumWidth(380)
        self._build_ui(current_amount)
        self._init_theme()

    def _build_ui(self, current_amount):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        self.intro = QLabel(t("dlg.payment.intro"))
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setMaximum(100000)
        self.amount_input.setPrefix("EGP ")
        self.amount_input.setValue(current_amount or 0.0)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setDate(QDate.currentDate())

        form.addRow(t("dlg.payment.amount"), self.amount_input)
        form.addRow(t("dlg.payment.date"), self.date_input)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        cancel_button = QPushButton(t("dlg.payment.cancel"))
        make_secondary(cancel_button)
        save_button = QPushButton(t("dlg.payment.save"))
        save_button.setDefault(True)
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    def restyle(self):
        tm = theme()
        self.intro.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
        )

    def get_values(self):
        qd = self.date_input.date()
        return self.amount_input.value(), date(qd.year(), qd.month(), qd.day())