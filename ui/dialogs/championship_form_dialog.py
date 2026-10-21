"""
Add / edit championship dialog — v5 design (matches the user dialog).

What changed from v4 (save logic and service calls are unchanged):
  * Header: trophy badge + live preview of the championship name and
    "activity · date", then a divider.
  * Required fields (name, activity, date) get a separate red asterisk via
    ui/form_helpers.FieldLabel — no more "*" glued onto Arabic text.
  * Invalid fields get a red border and focus when saving fails.
  * Notes is a multi-line box instead of a one-line field.
  * Editing a championship whose activity was later deactivated no longer
    silently re-assigns it to the first activity in the list.
  * No new translation keys.
"""
from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox,
    QDateEdit, QPushButton, QHBoxLayout, QLabel, QComboBox, QPlainTextEdit,
)
from qtpy.QtCore import Qt, QDate
from services import championship_service, activity_service
from ui.formatting import is_ar
from ui.theme import theme, ThemedWidget, make_secondary, polish_widget
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.form_helpers import FieldLabel, hex_, make_divider, style_divider


class ChampionshipFormDialog(ThemedWidget, QDialog):
    def __init__(self, championship=None, parent=None):
        QDialog.__init__(self, parent)
        self.championship = championship
        self.editing = championship is not None

        self._default_title = (
            t("champ.dialog.title_edit") if self.editing
            else t("champ.dialog.title_add")
        )
        self.setWindowTitle(self._default_title)
        self.setMinimumWidth(500)

        self._build_ui()
        if self.editing:
            self._prefill()
        self._refresh_header()
        self._init_theme()

        self.name_input.setFocus()

    # ---------- UI ----------

    def _build_ui(self):
        self._field_labels = []

        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        # ---- Header: trophy badge + live name / "activity · date" ----
        header = QHBoxLayout()
        header.setSpacing(SPACING["lg"])
        header.setContentsMargins(0, 0, 0, 0)

        self.badge = QLabel("🏆", self)
        self.badge.setFixedSize(56, 56)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.header_title = QLabel("", self)
        self.header_title.setWordWrap(True)
        self.header_sub = QLabel("", self)
        text_col.addStretch(1)
        text_col.addWidget(self.header_title)
        text_col.addWidget(self.header_sub)
        text_col.addStretch(1)

        header.addWidget(self.badge)
        header.addLayout(text_col, 1)
        root.addLayout(header)

        self.divider = make_divider(self, "champFormDivider")
        root.addWidget(self.divider)

        # ---- Form ----
        form = QFormLayout()
        form.setSpacing(SPACING["sm"])
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.name_input = QLineEdit(self)
        self.name_input.textChanged.connect(self._on_name_changed)

        # Activity combo — required. A championship must belong to an
        # activity so that "Assign Players" can filter eligible players.
        self.activity_combo = QComboBox(self)
        for act in activity_service.list_active():
            name = act.name_ar if is_ar() else act.name_en
            self.activity_combo.addItem(name, act.activity_id)
        self.activity_combo.currentIndexChanged.connect(self._on_activity_changed)

        self.date_input = QDateEdit(self)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setDate(QDate.currentDate())
        self.date_input.dateChanged.connect(lambda _d: self._refresh_header())

        self.location = QLineEdit(self)

        self.entry_fee = QDoubleSpinBox(self)
        self.entry_fee.setMinimum(0)
        self.entry_fee.setMaximum(99999)
        self.entry_fee.setDecimals(2)

        self.notes = QPlainTextEdit(self)
        self.notes.setFixedHeight(76)

        def add_row(key, widget, required=False):
            label = FieldLabel(t(key), required, self)
            self._field_labels.append(label)
            form.addRow(label, widget)

        add_row("champ.dialog.name", self.name_input, True)
        add_row("champ.dialog.activity", self.activity_combo, True)
        add_row("champ.dialog.date", self.date_input, True)
        add_row("champ.dialog.location", self.location)
        add_row("champ.dialog.fee", self.entry_fee)
        add_row("champ.dialog.notes", self.notes)

        root.addLayout(form)

        # ---- Error banner ----
        self.error_label = QLabel("", self)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

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
        save.clicked.connect(self._on_save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        root.addLayout(btns)

    # ---------- header / validation helpers ----------

    def _refresh_header(self):
        name = self.name_input.text().strip()
        self.header_title.setText(name or self._default_title)

        parts = []
        act = self.activity_combo.currentText().strip()
        if act:
            parts.append(act)
        d = self.date_input.date()
        parts.append(f"{d.year():04d}-{d.month():02d}-{d.day():02d}")
        self.header_sub.setText("  ·  ".join(parts))

    def _on_name_changed(self, _text=""):
        self._set_invalid(self.name_input, False)
        self._refresh_header()

    def _on_activity_changed(self, _index=0):
        self._set_invalid(self.activity_combo, False)
        self._refresh_header()

    @staticmethod
    def _set_invalid(widget, flag: bool):
        widget.setProperty("invalid", bool(flag))
        polish_widget(widget)

    # ---------- theme ----------

    def restyle(self):
        tm = theme()
        self.error_label.setStyleSheet(
            f"QLabel {{ color: {tm.color('danger')};"
            f" background-color: {tm.color('danger_soft')};"
            f" border-radius: {RADIUS['sm']}px; padding: 8px 12px; }}"
        )
        self.badge.setStyleSheet(
            f"QLabel {{ background-color: {hex_('primary_soft', 'primary', '#DBEAFE')};"
            f" border-radius: 28px; font-size: 26px; }}"
        )
        self.header_title.setStyleSheet(
            f"QLabel {{ color: {tm.color('text')}; font-size: 16px; font-weight: 700;"
            f" background: transparent; }}"
        )
        self.header_sub.setStyleSheet(
            f"QLabel {{ color: {tm.color('text_secondary')}; font-size: 12px;"
            f" background: transparent; }}"
        )
        style_divider(self.divider)
        for label in self._field_labels:
            label.apply_theme()

    # ---------- prefill ----------

    def _prefill(self):
        self.name_input.setText(self.championship.name)

        y, m, d = map(int, self.championship.event_date.split("-"))
        self.date_input.setDate(QDate(y, m, d))
        self.location.setText(self.championship.location or "")
        self.entry_fee.setValue(self.championship.entry_fee or 0.0)
        self.notes.setPlainText(self.championship.notes or "")

        if self.championship.activity_id:
            idx = self.activity_combo.findData(self.championship.activity_id)
            if idx >= 0:
                self.activity_combo.setCurrentIndex(idx)
            else:
                # The activity was deactivated after this championship was
                # created. Keep it selectable so saving doesn't silently
                # re-assign the championship to the first activity in the list.
                act = activity_service.get(self.championship.activity_id)
                if act is not None:
                    name = act.name_ar if is_ar() else act.name_en
                    self.activity_combo.addItem(name, act.activity_id)
                    self.activity_combo.setCurrentIndex(self.activity_combo.count() - 1)

    # ---------- save ----------

    def _on_save(self):
        self.error_label.hide()
        self._set_invalid(self.name_input, False)
        self._set_invalid(self.activity_combo, False)
        try:
            d = self.date_input.date()
            date_str = f"{d.year():04d}-{d.month():02d}-{d.day():02d}"

            name = self.name_input.text().strip()
            if not name:
                self._set_invalid(self.name_input, True)
                self.name_input.setFocus()
                raise ValueError(t("champ.dialog.error.name_required"))

            act_id = self.activity_combo.currentData()
            if act_id is None:
                self._set_invalid(self.activity_combo, True)
                self.activity_combo.setFocus()
                raise ValueError(t("champ.dialog.error.no_activity"))

            notes = self.notes.toPlainText().strip()

            if self.editing:
                championship_service.update_championship(
                    self.championship.championship_id,
                    name,
                    date_str,
                    act_id,
                    self.location.text().strip(),
                    self.entry_fee.value(),
                    notes,
                )
            else:
                championship_service.create_championship(
                    name,
                    date_str,
                    act_id,
                    self.location.text().strip(),
                    self.entry_fee.value(),
                    notes,
                )

            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))
            self.error_label.show()