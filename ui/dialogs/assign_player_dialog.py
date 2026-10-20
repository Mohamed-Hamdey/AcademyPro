"""
Assign Players Dialog — Fixed layout, Select All, Inline Editing.
"""
from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QDoubleSpinBox,
    QLineEdit, QPushButton, QLabel, QTableWidgetItem, QCheckBox,
    QWidget, QTableWidget, QHeaderView,QSizePolicy
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

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
        self.setMinimumSize(750, 550) # Wider to fit the columns nicely
        self._build_ui()
        self._init_theme()
        self._reload_players()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        root.setSpacing(SPACING["md"])

        # Search Bar
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("champ.assign.search"))
        self.search_input.setProperty("cssClass", "search")
        self.debouncer = Debouncer(250, self._reload_players, parent=self)
        self.search_input.textChanged.connect(self.debouncer.trigger)
        search_row.addWidget(self.search_input)
        root.addLayout(search_row)

        # Table
        self.table = make_standard_table(
            headers=["", t("champ.col.player"), t("champ.col.belt"), t("champ.col.weight")],
            column_modes=["fixed", "stretch", "fixed", "fixed"],
            parent=self,
        )
        # Force specific widths so the widgets have breathing room
        self.table.setColumnWidth(0, 60)   # Checkbox column
        self.table.setColumnWidth(2, 160)  # Belt column
        self.table.setColumnWidth(3, 150)  # Weight column
        

        
        self.table.verticalHeader().setDefaultSectionSize(68)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        
        # Add "Select All" checkbox in the header
        header = self.table.horizontalHeader()
        self.select_all_cb = QCheckBox()
        self.select_all_cb.setStyleSheet("margin-left: 10px;")
        self.select_all_cb.stateChanged.connect(self._on_select_all)
        
        # Wrap the header in a layout
        header_widget = QWidget()
        h_layout = QHBoxLayout(header_widget)
        h_layout.setContentsMargins(12, 0, 0, 0)
        h_layout.addWidget(self.select_all_cb)
        
        # We set the header item for col 0 to a widget (Qt doesn't support this natively well, 
        # so we just label it and put the checkbox below it, OR we can just rely on clicking the header).
        # Better approach: Just add the checkbox as a floating widget or use a custom header.
        # For simplicity, let's just make the column header blank and put a "Select All" button above.
        
        root.addWidget(self.table)

        # Select All Row (Placed above table for safety)
        select_all_row = QHBoxLayout()
        self.select_all_check = QCheckBox(t("champ.assign.select_all"))
        self.select_all_check.stateChanged.connect(self._on_select_all)
        select_all_row.addWidget(self.select_all_check)
        select_all_row.addStretch()
        root.addLayout(select_all_row)

        # Footer Actions
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(SPACING["md"])
        
        bottom_row.addWidget(QLabel(t("champ.assign.default_belt")))
        self.default_belt = QComboBox()
        for belt_key in ["white", "yellow", "orange", "green", "blue", "brown", "black"]:
            self.default_belt.addItem(t(f"belt.{belt_key}"), belt_key)
        bottom_row.addWidget(self.default_belt)
        
        bottom_row.addWidget(QLabel(t("champ.assign.default_weight")))
        self.default_weight = QDoubleSpinBox()
        self.default_weight.setMinimum(10)
        self.default_weight.setMaximum(300)
        self.default_weight.setValue(60)
        self.default_weight.setSuffix(t("champ.assign.weight_suffix"))
        bottom_row.addWidget(self.default_weight)
        
        bottom_row.addStretch()
        
        cancel_btn = QPushButton(t("msg.cancel"))
        make_secondary(cancel_btn)
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)
        
        self.save_btn = QPushButton(t("champ.assign.btn", n=0))
        self.save_btn.setDefault(True)
        self.save_btn.setEnabled(False)
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
        )

    def _reload_players(self):
        query = self.search_input.text().strip()
        
        # 1. Fetch eligible players
        if self.champ and self.champ.activity_id is not None:
            rows = players_repo.search_with_details_for_activity(self.champ.activity_id, query)
        else:
            rows = players_repo.search_with_details(query)

        self.table.setRowCount(len(rows))
        
        for i, r in enumerate(rows):
            p = r["player"]
            is_assigned = p.player_id in self.existing_ids

            # 1. Checkbox (Wrapped for spacing)
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(10, 0, 0, 0) # Add left margin
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(False)
            
            if is_assigned:
                chk.setEnabled(False)
                chk.setChecked(True)
            
            chk.stateChanged.connect(self._update_selected_count)
            chk_layout.addWidget(chk)
            self.table.setCellWidget(i, 0, chk_widget)

            # 2. Player Name
            name = p.full_name
            if is_assigned:
                name += f"  ({t('champ.assign.already')})"
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, p.player_id)
            
            if is_assigned:
                name_item.setForeground(QColor(theme().color("text_secondary")))
                
            self.table.setItem(i, 1, name_item)


            # 3. Belt — consistent height and alignment
            belt_container = QWidget()
            belt_layout = QHBoxLayout(belt_container)
            belt_layout.setContentsMargins(8, 3, 8, 3)
            belt_layout.setSpacing(0)

            belt_combo = QComboBox()
            belt_combo.setMinimumHeight(32)
            belt_combo.setMaximumHeight(32)
            belt_combo.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

            for belt_key in [
                "white", "yellow", "orange", "green",
                "blue", "brown", "black"
            ]:
                belt_combo.addItem(t(f"belt.{belt_key}"), belt_key)

            p_belt = getattr(p, "belt", "white") or "white"
            idx = belt_combo.findData(p_belt.lower())
            if idx >= 0:
                belt_combo.setCurrentIndex(idx)

            if is_assigned:
                belt_combo.setEnabled(False)

            belt_layout.addWidget(belt_combo)
            self.table.setCellWidget(i, 2, belt_container)

            # 4. Weight — consistent height and alignment
            weight_container = QWidget()
            weight_layout = QHBoxLayout(weight_container)
            weight_layout.setContentsMargins(8, 3, 8, 3)
            weight_layout.setSpacing(0)

            weight_spin = QDoubleSpinBox()
            weight_spin.setMinimum(10)
            weight_spin.setMaximum(300)
            weight_spin.setDecimals(1)
            weight_spin.setSingleStep(0.5)
            weight_spin.setMinimumHeight(32)
            weight_spin.setMaximumHeight(32)
            weight_spin.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            weight_spin.setSuffix(" kg")

            p_weight = getattr(p, "weight_kg", 60) or 60
            weight_spin.setValue(p_weight)

            if is_assigned:
                weight_spin.setEnabled(False)

            weight_layout.addWidget(weight_spin)
            self.table.setCellWidget(i, 3, weight_container)


        self._update_selected_count()

    def _on_select_all(self, state):
        checked = (state == Qt.CheckState.Checked.value)
        for i in range(self.table.rowCount()):
            w = self.table.cellWidget(i, 0)
            if w:
                chk = w.findChild(QCheckBox)
                if chk and chk.isEnabled():
                    chk.setChecked(checked)

    def _update_selected_count(self):
        count = 0
        for i in range(self.table.rowCount()):
            w = self.table.cellWidget(i, 0)
            if w:
                chk = w.findChild(QCheckBox)
                if chk and chk.isChecked() and chk.isEnabled():
                    count += 1
                    
        self.save_btn.setText(t("champ.assign.btn", n=count))
        self.save_btn.setEnabled(count > 0)

    def _on_save(self):
        self.error_label.hide()
        selected_count = 0
        
        try:
            for i in range(self.table.rowCount()):
                w = self.table.cellWidget(i, 0)
                chk = w.findChild(QCheckBox)
                
                if not chk or not chk.isChecked() or not chk.isEnabled():
                    continue
                    
                p_id = self.table.item(i, 1).data(Qt.ItemDataRole.UserRole)
                
                belt_combo = self.table.cellWidget(i, 2)
                weight_spin = self.table.cellWidget(i, 3)
                
                belt = belt_combo.currentData()
                weight = weight_spin.value()
                
                championship_service.register_player(
                    self.championship_id, 
                    p_id, 
                    weight, 
                    belt, 
                    "", 
                    record_payment=True
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