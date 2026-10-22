"""
Record Measurement Dialog — v5 design.
Captures a new weight and belt for a player's history.
"""
from datetime import date
from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox,
    QComboBox, QLineEdit, QPushButton, QWidget, QFrame
)
from qtpy.QtCore import Qt
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


def _col(name: str, fallback_token: str, default: str) -> str:
    try:
        pal = theme().palette()
        return pal.get(name) or pal.get(fallback_token) or default
    except Exception:
        return default


class _FieldLabel(QWidget):
    def __init__(self, text: str, required: bool = True, parent=None):
        QWidget.__init__(self, parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        self.text_lbl = QLabel((text or "").rstrip(" *"), self)
        lay.addWidget(self.text_lbl)
        self.star_lbl = QLabel("*", self) if required else None
        if self.star_lbl:
            lay.addWidget(self.star_lbl)
        lay.addStretch(1)
        self.apply_theme()

    def apply_theme(self):
        if self.star_lbl:
            color = _col("danger", "danger", "#DC2626")
            self.star_lbl.setStyleSheet(f"QLabel {{ color: {color}; font-weight: 700; }}")


class RecordMeasurementDialog(ThemedWidget, QDialog):
    def __init__(self, current_weight: float = 0.0, current_belt: str = "", 
                 requires_belt: bool = True, requires_weight: bool = True, parent=None):
        QDialog.__init__(self, parent)
        self._requires_belt = requires_belt
        self._requires_weight = requires_weight
        
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)

        try:
            self.setWindowTitle(t("players.measurement.dialog_title"))
            self.setMinimumWidth(380)
            self._build_ui(current_weight, current_belt)
            self._init_theme()
        finally:
            self.setUpdatesEnabled(True)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
            self.update()

    def _build_ui(self, current_weight, current_belt):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        # Weight (only if required)
        if self._requires_weight:
            self.weight_input = QDoubleSpinBox(self)
            self.weight_input.setRange(0, 300)
            self.weight_input.setSuffix(" kg")
            self.weight_input.setDecimals(1)
            self.weight_input.setValue(current_weight or 0.0)
            layout.addWidget(_FieldLabel(t("players.measurement.weight"), True, self))
            layout.addWidget(self.weight_input)
        else:
            self.weight_input = None

        # Belt (only if required)
        if self._requires_belt:
            self.belt_combo = QComboBox(self)
            belts = ["white", "yellow", "orange", "green", "blue", "purple", "brown", "black"]
            for b in belts:
                self.belt_combo.addItem(t(f"belt.{b}"), b)
            if current_belt:
                idx = self.belt_combo.findData(current_belt.lower())
                if idx >= 0:
                    self.belt_combo.setCurrentIndex(idx)
            layout.addWidget(_FieldLabel(t("players.measurement.belt"), False, self))
            layout.addWidget(self.belt_combo)
        else:
            self.belt_combo = None

        # Notes
        self.notes_input = QLineEdit(self)
        self.notes_input.setPlaceholderText(t("players.measurement.notes_placeholder"))
        layout.addWidget(_FieldLabel(t("players.measurement.notes"), False, self))
        layout.addWidget(self.notes_input)

        # Divider
        divider = QFrame(self)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {_col('divider', 'border', '#E8EDF3')}; border: none;")
        layout.addWidget(divider)

        # Buttons
        btns = QHBoxLayout()
        btns.setSpacing(SPACING["sm"])
        btns.addStretch()
        cancel = QPushButton(t("msg.cancel"), self)
        make_secondary(cancel)
        cancel.clicked.connect(self.reject)
        save = QPushButton(t("msg.save"), self)
        save.setDefault(True)
        save.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def get_values(self):
        weight = self.weight_input.value() if self.weight_input else None
        belt = self.belt_combo.currentData() if self.belt_combo else None
        notes = self.notes_input.text().strip() or None
        return weight, belt, notes