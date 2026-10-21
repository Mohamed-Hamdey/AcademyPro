"""
Custom dialog for editing a participant's championship result — v5 design.

Replaces the native QInputDialog so it follows the app's theme.
Small, focused dialog: header (player name) → divider → combo → buttons.
"""

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QFrame,
)
from qtpy.QtCore import Qt

from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS, TYPOGRAPHY
from ui.i18n import t


def _col(name: str, fallback_token: str, default: str) -> str:
    """Resolve a theme colour without ever raising."""
    try:
        pal = theme().palette()
        return pal.get(name) or pal.get(fallback_token) or default
    except Exception:
        return default


class EditResultDialog(ThemedWidget, QDialog):
    def __init__(self, current_result, player_name, parent=None):
        QDialog.__init__(self, parent)

        # Flash guard.
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)

        try:
            self.setWindowTitle(t("champ.detail.edit_result"))
            self.setMinimumWidth(400)

            self.current_result = current_result
            self.player_name = player_name

            self._build_ui()
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

        # ---- Header: player name ----
        self.name_lbl = QLabel(self.player_name, self)
        self.name_lbl.setWordWrap(True)
        layout.addWidget(self.name_lbl)

        # ---- Divider ----
        divider = QFrame(self)
        divider.setObjectName("editResultDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            f"QFrame#editResultDivider {{"
            f"  background-color: {_col('divider', 'border', '#E8EDF3')};"
            f"  border: none;"
            f"}}"
        )
        layout.addWidget(divider)

        # ---- Combo box for medal choices ----
        self.combo = QComboBox(self)
        self.choices = [
            ("gold", t("result.gold")),
            ("silver", t("result.silver")),
            ("bronze", t("result.bronze")),
            ("participant", t("result.participant")),
            (None, t("champ.result.none")),
        ]

        for i, (key, label) in enumerate(self.choices):
            self.combo.addItem(label, key)
            if key == self.current_result:
                self.combo.setCurrentIndex(i)

        layout.addWidget(self.combo)

        # ---- Buttons ----
        btns = QHBoxLayout()
        btns.setSpacing(SPACING["sm"])
        btns.setContentsMargins(0, SPACING["sm"], 0, 0)
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

    # ---------- theming ----------

    def restyle(self):
        tm = theme()
        self.name_lbl.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['section']['size']}px;"
            f"  font-weight: 600;"
            f"}}"
        )

    # ---------- result ----------

    def get_result(self):
        """Returns the selected result key (or None)."""
        return self.combo.currentData()