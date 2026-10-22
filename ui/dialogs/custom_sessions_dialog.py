"""
Custom Sessions Filter Dialog — v5 design (matches users_dialog v5).
Prompts the user for a session count to filter by.
"""

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QWidget, QFrame,
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


class CustomSessionsDialog(ThemedWidget, QDialog):
    def __init__(self, parent=None, default_count=8):
        QDialog.__init__(self, parent)

        # Flash guard.
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)

        try:
            self.setWindowTitle(t("players.filter.custom_sessions_title"))
            self.setMinimumWidth(380)
            self._build_ui(default_count)
            self._init_theme()
        finally:
            self.setUpdatesEnabled(True)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
            self.update()

    def _build_ui(self, default_count):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["md"])

        # ---- Form ----
        self.label = _FieldLabel(t("players.filter.custom_sessions_prompt"), True, self)
        layout.addWidget(self.label)

        self.spin = QSpinBox(self)
        self.spin.setRange(1, 999)
        self.spin.setValue(default_count)
        layout.addWidget(self.spin)

        # ---- Divider ----
        divider = QFrame(self)
        divider.setObjectName("customSessDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            f"QFrame#customSessDivider {{"
            f"  background-color: {_col('divider', 'border', '#E8EDF3')};"
            f"  border: none;"
            f"}}"
        )
        layout.addWidget(divider)

        # ---- Buttons ----
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        button_row.setContentsMargins(0, SPACING["sm"], 0, 0)

        cancel_button = QPushButton(t("msg.cancel"), self)
        make_secondary(cancel_button)
        cancel_button.clicked.connect(self.reject)

        save_button = QPushButton(t("msg.ok"), self) # Assuming you have a msg.ok, otherwise use t("msg.save")
        save_button.setDefault(True)
        save_button.clicked.connect(self.accept)

        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    def get_value(self) -> int:
        return self.spin.value()