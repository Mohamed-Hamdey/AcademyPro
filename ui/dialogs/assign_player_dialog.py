"""
Multi-player assignment dialog for championships.
"""
from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QDoubleSpinBox,
    QLineEdit, QPushButton, QLabel, QTableWidgetItem, QCheckBox,
    QWidget, QTableWidget,
)
from qtpy.QtCore import Qt
from repositories import players_repo, championships_repo
from services import championship_service
from ui.table_helpers import make_standard_table
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING
from ui.i18n import t
from ui.utils import Debouncer


class AssignPlayerDialog(ThemedWidget, QDialog):
    def __init__(self, championship_id, existing_player_ids, parent=None):
        QDialog.__init__(self, parent)
        self.championship_id = championship_id
        self.existing_ids = set(existing_player_ids)
        self.champ = championships_repo.get_championship(self.championship_id)
        self.setWindowTitle(t("champ.assign.title"))
        self.setMinimumSize(650, 500)
        self._build_ui()
        self._init_theme()
        self._reload_players()
        self.table.cellClicked.connect(self._on_cell_clicked)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        # --- Search Bar ---
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("champ.assign.search"))
        self.search_input.setProperty("cssClass", "search")

        self.debouncer = Debouncer(250, self._reload_players, parent=self)
        self.search_input.textChanged.connect(self.debouncer.trigger)

        search_row.addWidget(self.search_input)
        root.addLayout(search_row)

        # --- Player Table ---
        self.table = make_standard_table(
            headers=[
                "",
                t("champ.col.player"),
                t("champ.col.belt"),
                t("champ.col.weight"),
            ],
            column_modes=["fixed", "stretch", "resize", "resize"],
            parent=self,
        )
        self.table.setColumnWidth(0, 50)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        root.addWidget(self.table, stretch=1)

        # --- Defaults & Buttons ---
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(SPACING["md"])

        bottom_row.addWidget(QLabel(t("champ.assign.default_belt")))
        self.default_belt = QComboBox()
        for belt_key in ["white", "yellow", "orange", "green",
                         "blue", "brown", "black"]:
            # Store the lowercase KEY as data — display is localized.
            self.default_belt.addItem(t(f"belt.{belt_key}"), belt_key)
        bottom_row.addWidget(self.default_belt)

        bottom_row.addWidget(QLabel(t("champ.assign.default_weight")))
        self.default_weight = QDoubleSpinBox()
        self.default_weight.setMinimum(1)
        self.default_weight.setMaximum(300)
        self.default_weight.setValue(60)
        self.default_weight.setSuffix(" kg")
        bottom_row.addWidget(self.default_weight)

        bottom_row.addStretch()

        cancel_btn = QPushButton(t("msg.cancel"))
        make_secondary(cancel_btn)
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)

        self.save_btn = QPushButton(t("champ.assign.confirm"))
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)
        bottom_row.addWidget(self.save_btn)

        root.addLayout(bottom_row)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red; font-size: 12px;")
        self.error_label.hide()
        root.addWidget(self.error_label)

    def restyle(self):
        tm = theme()
        self.table.setStyleSheet(
            f"QTableWidget {{"
            f"  selection-background-color: {tm.color('primary_soft')};"
            f"  selection-color: {tm.color('text')};"
            f"}}"
            f"QTableWidget::item:selected {{"
            f"  background-color: {tm.color('primary_soft')};"
            f"  color: {tm.color('text')};"
            f"}}"
            f"QTableWidget::item:hover:!selected {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"}}"
        )

    def _reload_players(self):
        """
        One batch call — no N+1. Uses the existing repo helpers:

            players_repo.search_with_details_for_activity(act_id, query)
            players_repo.search_with_details(query)

        Both return [{ "player": Player, ... , "activity_names": [...] }, ...].
        We filter out already-assigned players, then populate the table.
        """
        query = self.search_input.text().strip()


        rows = players_repo.search_with_details(query)

        # Filter out players already in the championship.
        rows = [r for r in rows if r["player"].player_id not in self.existing_ids]

        self.table.setRowCount(len(rows))

        # --- NEW: عرض رسالة إذا كانت القائمة فارغة ---
        if not rows:
            self.table.hide()
            if not hasattr(self, 'empty_label'):
                from qtpy.QtWidgets import QLabel
                self.empty_label = QLabel(self)
                self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.empty_label.setStyleSheet("color: gray; font-style: italic;")
                root = self.layout()
                if root:
                    root.addWidget(self.empty_label)
            
            self.empty_label.setText(t("champ.assign.empty"))
            self.empty_label.show()
            return
        else:
            self.table.show()
            if hasattr(self, 'empty_label'):
                self.empty_label.hide()
        # ---------------------------------------------

        for i, r in enumerate(rows):
            p = r["player"]

            # --- Checkbox column ---
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox()
            chk_layout.addWidget(chk)
            self.table.setCellWidget(i, 0, chk_widget)

            # --- Player name (with player_id stashed for save) ---
            name_item = QTableWidgetItem(p.full_name)
            name_item.setData(Qt.ItemDataRole.UserRole, p.player_id)
            self.table.setItem(i, 1, name_item)

            # --- Belt (default; per-player editing happens on detail screen) ---
            self.table.setItem(
                i, 2,
                QTableWidgetItem(t(f"belt.{self.default_belt.currentData()}")),
            )

            # --- Weight (default) ---
            self.table.setItem(
                i, 3,
                QTableWidgetItem(f"{self.default_weight.value():.0f} kg"),
            )

    def _on_cell_clicked(self, row, col):
        if col == 0:
            return  # native checkbox click handles itself
        chk_widget = self.table.cellWidget(row, 0)
        if chk_widget:
            chk = chk_widget.layout().itemAt(0).widget()
            if chk is not None:
                chk.setChecked(not chk.isChecked())

    def _on_save(self):
        self.error_label.hide()
        selected_count = 0

        try:
            for i in range(self.table.rowCount()):
                chk_widget = self.table.cellWidget(i, 0)
                chk = chk_widget.layout().itemAt(0).widget()
                if chk is None or not chk.isChecked():
                    continue

                p_id = self.table.item(i, 1).data(Qt.ItemDataRole.UserRole)

                championship_service.register_player(
                    self.championship_id,
                    p_id,
                    self.default_weight.value(),
                    self.default_belt.currentData(),   # lowercase key
                    "",
                    record_payment=True,
                )
                selected_count += 1

            if selected_count == 0:
                self.error_label.setText(t("champ.assign.error.none_selected"))
                self.error_label.show()
                return

            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))
            self.error_label.show()