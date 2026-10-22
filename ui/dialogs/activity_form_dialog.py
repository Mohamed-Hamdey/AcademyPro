"""
Add / edit activity dialog — v5 design (matches users_dialog v5).

Fields:
  * English name
  * Arabic name
  * Training days (multi-select checkboxes)
  * Optional color (hex, used for badges later)
"""

import os
import sys

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QHBoxLayout, QLabel, QCheckBox, QWidget, QGridLayout, QColorDialog,
    QFrame,
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

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


class ActivityFormDialog(ThemedWidget, QDialog):
    def __init__(self, activity=None, parent=None):
        QDialog.__init__(self, parent)

        # Flash guard.
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)

        try:
            self.editing = activity is not None
            self.activity = activity
            self._selected_color = activity.color if activity else None

            self.setWindowTitle(
                t("activities.dialog.title_edit") if self.editing
                else t("activities.dialog.title_add")
            )
            self.setMinimumWidth(540)

            self._build_ui()
            if activity:
                self._prefill(activity)
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

        # ---- Text fields ----
        self.name_input = QLineEdit(self) # Replaces name_en and name_ar


        # ---- Training days ----
        days_container = QWidget(self)
        days_grid = QGridLayout(days_container)
        days_grid.setContentsMargins(0, 0, 0, 0)
        days_grid.setSpacing(SPACING["xs"])

        self.day_checkboxes = {}
        for i, (day_key, day_label_key) in enumerate(WEEKDAYS):
            cb = QCheckBox(t(day_label_key), self)
            self.day_checkboxes[day_key] = cb
            days_grid.addWidget(cb, i // 4, i % 4)

        # ---- Color picker (optional) ----
        color_row = QHBoxLayout()
        color_row.setSpacing(SPACING["sm"])
        color_row.setContentsMargins(0, 0, 0, 0)
        self.color_button = QPushButton(t("activities.dialog.pick_color"), self)
        make_secondary(self.color_button)
        self.color_button.clicked.connect(self._pick_color)
        self.color_preview = QLabel(self)
        self.color_preview.setFixedSize(28, 28)
        color_row.addWidget(self.color_button)
        color_row.addWidget(self.color_preview)
        color_row.addStretch()

        # ---- Requirements (v4) ----
        self.requires_belt_cb = QCheckBox(t("activities.dialog.requires_belt"), self)
        self.requires_weight_cb = QCheckBox(t("activities.dialog.requires_weight"), self)
        self.requires_belt_cb.setChecked(True)
        self.requires_weight_cb.setChecked(True)

        # ---- Form rows with asterisks ----
        form.addRow(_FieldLabel(t("activities.dialog.name"), True, self), self.name_input)
        form.addRow(_FieldLabel(t("activities.dialog.days"), False, self), days_container)
        form.addRow(_FieldLabel(t("activities.dialog.color"), False, self), color_row)
        form.addRow(_FieldLabel("", False, self), self.requires_belt_cb)
        form.addRow(_FieldLabel("", False, self), self.requires_weight_cb)
        layout.addLayout(form)

        # ---- Divider ----
        divider = QFrame(self)
        divider.setObjectName("activityFormDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            f"QFrame#activityFormDivider {{"
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
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        button_row.setContentsMargins(0, SPACING["sm"], 0, 0)

        cancel_button = QPushButton(t("activities.dialog.cancel"), self)
        make_secondary(cancel_button)

        save_button = QPushButton(t("activities.dialog.save"), self)
        save_button.setDefault(True)
        save_button.clicked.connect(self._on_save)
        cancel_button.clicked.connect(self.reject)

        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

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
        self._update_color_preview()

    # ---------- prefill ----------

    def _prefill(self, activity):
        self.name_input.setText(activity.name)

        for day_key in (activity.default_days or []):
            cb = self.day_checkboxes.get(day_key)
            if cb:
                cb.setChecked(True)
        
        # FIX: Use dot notation, not dictionary brackets
        self.requires_belt_cb.setChecked(bool(activity.requires_belt))
        self.requires_weight_cb.setChecked(bool(activity.requires_weight))
        self._update_color_preview()

    # ---------- color ----------

    def _pick_color(self):
        initial = QColor(self._selected_color) if self._selected_color else QColor("#2563EB")
        color = QColorDialog.getColor(
            initial, self, t("activities.dialog.pick_color")
        )
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

    # ---------- save ----------

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()

    def _on_save(self):
        self.error_label.hide()

        name = self.name_input.text().strip()
        days = [day for day, cb in self.day_checkboxes.items() if cb.isChecked()]
        
        if not name:
            self._show_error(t("activities.dialog.error.name_required"))
            return

        try:
            if self.editing:
                activity_service.update(
                    self.activity.activity_id,
                    name=name,
                    default_days=days,
                    color=self._selected_color,
                    requires_belt=self.requires_belt_cb.isChecked(),
                    requires_weight=self.requires_weight_cb.isChecked(),
                )
            else:
                activity_service.create(
                    name=name,
                    default_days=days,
                    color=self._selected_color,
                    requires_belt=self.requires_belt_cb.isChecked(),
                    requires_weight=self.requires_weight_cb.isChecked(),
                )
        except ValueError as e:
            self._show_error(str(e))
            return
        except Exception as e:
            self._show_error(str(e))
            return

        self.accept()