"""
Add / edit activity dialog — v4 design.

Fields:
  * English name
  * Arabic name
  * Training days (multi-select checkboxes)
  * Optional color (hex, used for badges later)
"""

import os
import sys

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QHBoxLayout, QLabel, QCheckBox, QWidget, QGridLayout, QColorDialog,
)
from PyQt6.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import activity_service
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


class ActivityFormDialog(ThemedWidget, QDialog):
    def __init__(self, activity=None, parent=None):
        QDialog.__init__(self, parent)
        self.editing = activity is not None
        self.activity = activity
        self._selected_color = activity.color if activity else None

        self.setWindowTitle(
            t("activities.dialog.title_edit") if self.editing
            else t("activities.dialog.title_add")
        )
        self.setMinimumWidth(440)

        self._build_ui()
        if activity:
            self._prefill(activity)
        self._init_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])

        self.name_en_input = QLineEdit()
        self.name_ar_input = QLineEdit()

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

        # ---- Color picker (optional) ----
        color_row = QHBoxLayout()
        color_row.setSpacing(SPACING["sm"])
        self.color_button = QPushButton(t("activities.dialog.pick_color"))
        make_secondary(self.color_button)
        self.color_button.clicked.connect(self._pick_color)
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(28, 28)
        color_row.addWidget(self.color_button)
        color_row.addWidget(self.color_preview)
        color_row.addStretch()

        form.addRow(t("activities.dialog.name_en"), self.name_en_input)
        form.addRow(t("activities.dialog.name_ar"), self.name_ar_input)
        form.addRow(t("activities.dialog.days"), days_container)
        form.addRow(t("activities.dialog.color"), color_row)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        cancel_button = QPushButton(t("activities.dialog.cancel"))
        make_secondary(cancel_button)
        save_button = QPushButton(t("activities.dialog.save"))
        save_button.setDefault(True)
        save_button.clicked.connect(self._on_save)
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

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
        self._update_color_preview()

    def _prefill(self, activity):
        self.name_en_input.setText(activity.name_en)
        self.name_ar_input.setText(activity.name_ar)
        for day_key in activity.default_days:
            cb = self.day_checkboxes.get(day_key)
            if cb:
                cb.setChecked(True)
        self._update_color_preview()

    def _pick_color(self):
        initial = QColor(self._selected_color) if self._selected_color else QColor("#2563EB")
        color = QColorDialog.getColor(initial, self, t("activities.dialog.pick_color"))
        if color.isValid():
            self._selected_color = color.name()
            self._update_color_preview()

    def _update_color_preview(self):
        tm = theme()
        if self._selected_color:
            self.color_preview.setStyleSheet(
                f"QLabel {{"
                f"  background-color: {self._selected_color};"
                f"  border: 1px solid {tm.color('border')};"
                f"  border-radius: {RADIUS['xs']}px;"
                f"}}"
            )
        else:
            self.color_preview.setStyleSheet(
                f"QLabel {{"
                f"  background-color: transparent;"
                f"  border: 1px dashed {tm.color('border')};"
                f"  border-radius: {RADIUS['xs']}px;"
                f"}}"
            )

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()

    def _on_save(self):
        self.error_label.hide()

        name_en = self.name_en_input.text().strip()
        name_ar = self.name_ar_input.text().strip()
        days = [day for day, cb in self.day_checkboxes.items() if cb.isChecked()]

        try:
            if self.editing:
                activity_service.update(
                    self.activity.activity_id,
                    name_en=name_en,
                    name_ar=name_ar,
                    default_days=days,
                    color=self._selected_color,
                )
            else:
                activity_service.create(
                    name_en=name_en,
                    name_ar=name_ar,
                    default_days=days,
                    color=self._selected_color,
                )
        except ValueError as e:
            self._show_error(str(e))
            return
        except Exception as e:
            self._show_error(str(e))
            return

        self.accept()