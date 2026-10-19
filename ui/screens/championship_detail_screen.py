"""
Championship Detail Screen (Master-Detail).
"""
import os
import sys
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidgetItem, QComboBox, QScrollArea, QFrame, QMessageBox
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import championships_repo
from services import championship_service
from ui.dialogs.assign_player_dialog import AssignPlayerDialog
from ui.table_helpers import make_standard_table
from ui.components import SectionCard, KpiCard
from ui.theme import theme, ThemedWidget, make_danger
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.message_box import warn, ask


class ChampionshipDetailScreen(ThemedWidget, QWidget):
    def __init__(self, championship_id, on_back=None, parent=None):
        QWidget.__init__(self, parent)
        self.champ_id = championship_id
        self.on_back = on_back
        self._build_ui()
        self.refresh()
        self._init_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        # Header row
        header = QHBoxLayout()
        self.title_label = QLabel()
        header.addWidget(self.title_label)
        header.addStretch()
        
        self.edit_btn = QPushButton(t("champ.detail.edit"))
        self.edit_btn.clicked.connect(self._on_edit)
        header.addWidget(self.edit_btn)
        
        self.back_btn = QPushButton(t("champ.detail.back"))
        self.back_btn.clicked.connect(self._on_back)
        header.addWidget(self.back_btn)
        
        root.addLayout(header)

        # KPIs
        kpi_row = QHBoxLayout()
        self.participants_kpi = KpiCard(t("champ.detail.participants"), "0", value_color="primary")
        self.fees_kpi = KpiCard(t("champ.detail.total_fees"), "0 EGP", value_color="success")
        kpi_row.addWidget(self.participants_kpi, stretch=1)
        kpi_row.addWidget(self.fees_kpi, stretch=1)
        root.addLayout(kpi_row)

        # Table Card
        self.table_card = SectionCard(title=t("champ.detail.assigned_players"))
        
        self.table = make_standard_table(
            headers=[
                t("champ.col.player"),
                t("champ.col.weight"),
                t("champ.col.belt"),
                t("champ.col.result"),
            ],
            column_modes=["stretch", "resize", "resize", "resize"],
            parent=self,
        )
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table_card.body.addWidget(self.table)
        
        # Action row
        actions = QHBoxLayout()
        self.remove_btn = QPushButton(t("champ.detail.remove"))
        make_danger(self.remove_btn)
        self.remove_btn.clicked.connect(self._on_remove)
        self.remove_btn.setEnabled(False)
        
        self.edit_result_btn = QPushButton(t("champ.detail.edit_result"))
        self.edit_result_btn.clicked.connect(self._on_edit_result)
        self.edit_result_btn.setEnabled(False)
        
        self.assign_btn = QPushButton(t("champ.detail.assign"))
        self.assign_btn.clicked.connect(self._on_assign)
        
        actions.addWidget(self.edit_result_btn)
        actions.addWidget(self.remove_btn)
        actions.addStretch()
        actions.addWidget(self.assign_btn)
        self.table_card.body.addLayout(actions)

        root.addWidget(self.table_card, stretch=1)

    def restyle(self):
        tm = theme()
        self.title_label.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {tm.color('text')};")
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

    def refresh(self):
        champ = championships_repo.get_championship(self.champ_id)
        if not champ: return
        
        self.title_label.setText(champ.name)
        self.current_champ = champ
        
        parts = championship_service.get_participants(self.champ_id)
        self._rows = parts
        
        self.participants_kpi.set_value(str(len(parts)))
        total_fees = len(parts) * (champ.entry_fee or 0)
        self.fees_kpi.set_value(f"{total_fees:,.0f} EGP")
        
        self.table.setRowCount(len(parts))
        for i, p in enumerate(parts):
            name_item = QTableWidgetItem(p["full_name"])
            name_item.setData(Qt.ItemDataRole.UserRole, p["id"])
            self.table.setItem(i, 0, name_item)
            
            self.table.setItem(i, 1, QTableWidgetItem(f"{p['weight_kg']} kg" if p['weight_kg'] else "—"))
            self.table.setItem(i, 2, QTableWidgetItem(p['belt'] or "—"))
            self.table.setItem(i, 3, QTableWidgetItem(p['result'] or "—"))
            
        self._update_actions()

    def _selected_participant(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows: return None
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._rows): return None
        return self._rows[idx]

    def _update_actions(self):
        has = self._selected_participant() is not None
        self.remove_btn.setEnabled(has)
        self.edit_result_btn.setEnabled(has)

    def _on_back(self):
        if self.on_back: self.on_back()

    def _on_edit(self):
        from ui.dialogs.championship_form_dialog import ChampionshipFormDialog
        dlg = ChampionshipFormDialog(self.current_champ, parent=self)
        if dlg.exec(): self.refresh()

    def _on_assign(self):
        existing_ids = [p["player_id"] for p in self._rows]
        dlg = AssignPlayerDialog(self.champ_id, existing_ids, parent=self)
        if dlg.exec(): self.refresh()

    def _on_remove(self):
        p = self._selected_participant()
        if p and ask(self, t("champ.confirm.remove_title"), t("champ.confirm.remove_msg", name=p['full_name'])):
            championships_repo.remove_participant(p["id"])
            self.refresh()

    def _on_edit_result(self):
        p = self._selected_participant()
        if not p: return
        # Quick edit result via a simple dialog or combo
        from qtpy.QtWidgets import QInputDialog
        items = [t("result.gold"), t("result.silver"), t("result.bronze"), t("result.participant")]
        res, ok = QInputDialog.getItem(self, t("champ.detail.edit_result"), t("champ.col.result"), 
                                       items, 0, False)
        if ok and res:
            from models.championship import ChampionshipParticipant
            obj = championships_repo.get_participant(p["id"])
            obj.result = res
            championships_repo.update_participant(obj)
            self.refresh()