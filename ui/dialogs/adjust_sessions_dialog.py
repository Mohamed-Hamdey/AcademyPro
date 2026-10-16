"""Adjust sessions-remaining dialog — v4 design."""

import os
import sys

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QSpinBox, QPushButton,
    QHBoxLayout, QLabel,
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING
from ui.i18n import t


class AdjustSessionsDialog(ThemedWidget, QDialog):
    def __init__(self, subscription_id: int, current_value: int, total: int, parent=None):
        QDialog.__init__(self, parent)
        self.subscription_id = subscription_id
        self.setWindowTitle(t("dlg.adjust.title"))
        self.setMinimumWidth(360)
        self._build_ui(current_value, total)
        self._init_theme()

    def _build_ui(self, current_value, total):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        self.plan_total_label = QLabel(t("dlg.adjust.plan_total", total=total))
        layout.addWidget(self.plan_total_label)

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])
        self.value_input = QSpinBox()
        self.value_input.setRange(0, total)
        self.value_input.setValue(current_value)
        form.addRow(t("dlg.adjust.remaining"), self.value_input)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        cancel_button = QPushButton(t("dlg.adjust.cancel"))
        make_secondary(cancel_button)
        save_button = QPushButton(t("dlg.adjust.save"))
        save_button.setDefault(True)
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    def restyle(self):
        tm = theme()
        self.plan_total_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
        )

    def new_value(self) -> int:
        return self.value_input.value()