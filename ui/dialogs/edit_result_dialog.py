"""
Custom dialog for editing a participant's championship result.
Replaces the native QInputDialog so it follows the app's theme.
"""
from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
)
from qtpy.QtCore import Qt
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


class EditResultDialog(ThemedWidget, QDialog):
    def __init__(self, current_result, player_name, parent=None):
        QDialog.__init__(self, parent)

        self.setWindowTitle(t("champ.detail.edit_result"))
        self.setMinimumWidth(320)

        self.current_result = current_result
        self.player_name = player_name

        self._build_ui()
        self._init_theme()
        self.restyle()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        # Player name header
        name_lbl = QLabel(self.player_name)
        name_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(name_lbl)

        # Combo box for choices
        self.combo = QComboBox()
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
        
        self.combo.setMinimumHeight(36)
        layout.addWidget(self.combo)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        
        cancel = QPushButton(t("msg.cancel"))
        make_secondary(cancel)
        cancel.clicked.connect(self.reject)
        
        save = QPushButton(t("msg.save"))
        save.setDefault(True)
        save.clicked.connect(self.accept)
        
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def restyle(self):
        tm = theme()

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {tm.color('surface')};
                color: {tm.color('text')};
            }}

            QLabel {{
                color: {tm.color('text')};
            }}

            QComboBox {{
                background-color: {tm.color('surface_alt')};
                color: {tm.color('text')};
                border: 1px solid {tm.color('border')};
                border-radius: {RADIUS['sm']}px;
                padding: 4px 8px;
                min-height: 26px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {tm.color('surface')};
                color: {tm.color('text')};
                selection-background-color: {tm.color('surface_alt')};
                selection-color: {tm.color('text')};
                border: 1px solid {tm.color('border')};
            }}
        """)

    def get_result(self):
        """Returns the selected result key (or None)."""
        return self.combo.currentData()