"""
Add / edit championship dialog.
"""
from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox,
    QDateEdit, QPushButton, QHBoxLayout, QLabel, QComboBox,
)
from qtpy.QtCore import QDate
from services import championship_service, activity_service
from ui.formatting import is_ar
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


class ChampionshipFormDialog(ThemedWidget, QDialog):
    def __init__(self, championship=None, parent=None):
        QDialog.__init__(self, parent)
        self.championship = championship
        self.editing = championship is not None

        self.setWindowTitle(
            t("champ.dialog.title_edit") if self.editing
            else t("champ.dialog.title_add")
        )
        self.setMinimumWidth(450)
        self._build_ui()
        if self.editing:
            self._prefill()
        self._init_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        form = QFormLayout()
        form.setSpacing(SPACING["sm"])

        self.name_input = QLineEdit()

        # Activity combo — required. A championship must belong to an
        # activity so that "Assign Players" can filter eligible players.
        self.activity_combo = QComboBox()
        for act in activity_service.list_active():
            name = act.name_ar if is_ar() else act.name_en
            self.activity_combo.addItem(name, act.activity_id)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setDate(QDate.currentDate())

        self.location = QLineEdit()

        self.entry_fee = QDoubleSpinBox()
        self.entry_fee.setMinimum(0)
        self.entry_fee.setMaximum(99999)
        self.entry_fee.setDecimals(2)

        self.notes = QLineEdit()

        form.addRow(t("champ.dialog.name"), self.name_input)
        form.addRow(t("champ.dialog.activity"), self.activity_combo)
        form.addRow(t("champ.dialog.date"), self.date_input)
        form.addRow(t("champ.dialog.location"), self.location)
        form.addRow(t("champ.dialog.fee"), self.entry_fee)
        form.addRow(t("champ.dialog.notes"), self.notes)

        root.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton(t("msg.cancel"))
        make_secondary(cancel)
        cancel.clicked.connect(self.reject)
        save = QPushButton(t("msg.save"))
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        root.addLayout(btns)

    def restyle(self):
        tm = theme()
        self.error_label.setStyleSheet(
            f"QLabel {{ color: {tm.color('danger')};"
            f" background-color: {tm.color('danger_soft')};"
            f" border-radius: {RADIUS['sm']}px; padding: 8px; }}"
        )

    def _prefill(self):
        self.name_input.setText(self.championship.name)

        y, m, d = map(int, self.championship.event_date.split("-"))
        self.date_input.setDate(QDate(y, m, d))
        self.location.setText(self.championship.location or "")
        self.entry_fee.setValue(self.championship.entry_fee or 0.0)
        self.notes.setText(self.championship.notes or "")

        if self.championship.activity_id:
            idx = self.activity_combo.findData(self.championship.activity_id)
            if idx >= 0:
                self.activity_combo.setCurrentIndex(idx)

    def _on_save(self):
        self.error_label.hide()
        try:
            d = self.date_input.date()
            date_str = f"{d.year():04d}-{d.month():02d}-{d.day():02d}"

            name = self.name_input.text().strip()
            if not name:
                raise ValueError(t("champ.dialog.error.name_required"))

            act_id = self.activity_combo.currentData()
            if act_id is None:
                raise ValueError(t("champ.dialog.error.no_activity"))

            if self.editing:
                championship_service.update_championship(
                    self.championship.championship_id,
                    name,
                    date_str,
                    act_id,
                    self.location.text().strip(),
                    self.entry_fee.value(),
                    self.notes.text().strip(),
                )
            else:
                championship_service.create_championship(
                    name,
                    date_str,
                    act_id,
                    self.location.text().strip(),
                    self.entry_fee.value(),
                    self.notes.text().strip(),
                )

            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))
            self.error_label.show()