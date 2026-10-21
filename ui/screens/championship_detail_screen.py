"""
Championship Detail Screen — KPI Strip, Medal Pills, and Export.
"""
import os
import sys
import csv
from datetime import date
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidgetItem, QInputDialog, QFileDialog, QTableWidget
)
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QColor
from ui.components import SectionCard, KpiCard, EmptyState, Toolbar, PillDelegate
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import championships_repo
from services import championship_service, activity_service
from ui.dialogs.assign_player_dialog import AssignPlayerDialog
from ui.dialogs.championship_form_dialog import ChampionshipFormDialog
from ui.table_helpers import make_standard_table
from ui.components import SectionCard, KpiCard, EmptyState, Toolbar
from ui.theme import theme, ThemedWidget, make_danger, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.message_box import info, ask, warn
from ui.dialogs.edit_result_dialog import EditResultDialog

class ChampionshipDetailScreen(ThemedWidget, QWidget):
    def __init__(self, championship_id, on_back=None, parent=None):
        QWidget.__init__(self, parent)
        self.champ_id = championship_id
        self.on_back = on_back
        self._rows = []
        self._build_ui()
        self.refresh()
        self._init_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        # --- Header ---
        header = QHBoxLayout()
        self.title_label = QLabel()
        header.addWidget(self.title_label)
        header.addStretch()

        self.edit_btn = QPushButton(t("champ.detail.edit"))
        make_secondary(self.edit_btn)
        self.edit_btn.clicked.connect(self._on_edit)
        header.addWidget(self.edit_btn)

        self.back_btn = QPushButton(t("champ.detail.back"))
        self.back_btn.clicked.connect(self._on_back)
        header.addWidget(self.back_btn)
        root.addLayout(header)

        # --- KPI Strip ---
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(SPACING["sm"])
        
        self.kpi_participants = KpiCard(t("champ.detail.kpi.participants"), "0")
        self.kpi_gold = KpiCard(t("champ.detail.kpi.gold"), "0", value_color="medal_gold")
        self.kpi_silver = KpiCard(t("champ.detail.kpi.silver"), "0", value_color="medal_silver")
        self.kpi_bronze = KpiCard(t("champ.detail.kpi.bronze"), "0", value_color="medal_bronze")
        self.kpi_fee = KpiCard(t("champ.detail.kpi.fee"), "0 EGP")
        
        for kpi in (self.kpi_participants, self.kpi_gold, self.kpi_silver, self.kpi_bronze, self.kpi_fee):
            kpi_row.addWidget(kpi, stretch=1)
        root.addLayout(kpi_row)

        # --- Table Card ---
        self.table_card = SectionCard(title=t("champ.detail.assigned_players"))
        
        self.table = make_standard_table(
            headers=[
                t("champ.col.player"),
                t("champ.col.belt"),
                t("champ.col.weight"),
                t("champ.col.result"),
            ],
            # Give Result a healthy fixed width (e.g., 100px)
            column_modes=["stretch", "resize", "resize", "fixed"],
            parent=self,
        )
        self.table.setColumnWidth(3, 110)
        self._pill_delegate = PillDelegate(self.table)
        self.table.setItemDelegateForColumn(3, self._pill_delegate)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.itemDoubleClicked.connect(self._on_edit_result)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table_card.body.addWidget(self.table)

        self.empty_label = EmptyState(icon="👥", message=t("champ.detail.empty"))
        self.empty_label.hide()
        self.table_card.body.addWidget(self.empty_label)

        # --- Actions Row ---
        actions = QHBoxLayout()
        self.remove_btn = QPushButton(t("champ.detail.remove"))
        make_danger(self.remove_btn)
        self.remove_btn.clicked.connect(self._on_remove)
        self.remove_btn.setEnabled(False)
        
        self.assign_btn = QPushButton(t("champ.detail.action.assign"))
        self.assign_btn.clicked.connect(self._on_assign)
        
        self.export_btn = QPushButton(t("champ.detail.export"))
        make_secondary(self.export_btn)
        self.export_btn.clicked.connect(self._on_export)
        
        self.delete_btn = QPushButton(t("champ.detail.action.delete"))
        make_danger(self.delete_btn)
        self.delete_btn.clicked.connect(self._on_delete)

        actions.addWidget(self.delete_btn)
        actions.addWidget(self.remove_btn)
        actions.addStretch()
        actions.addWidget(self.export_btn)
        actions.addWidget(self.assign_btn)
        self.table_card.body.addLayout(actions)

        root.addWidget(self.table_card, stretch=1)

    def restyle(self):
        tm = theme()
        self.title_label.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {tm.color('text')};")
        self.table.setStyleSheet(
            f"QTableWidget {{"
            f"  selection-background-color: {tm.color('primary_soft')};"
            f"  selection-color: {tm.color('text')};"
            f"}}"
            f"QTableWidget::item:selected {{"
            f"  background-color: {tm.color('primary_soft')};"
            f"  color: {tm.color('text')};"
            f"}}"
        )

    def refresh(self):
        champ = championships_repo.get_championship(self.champ_id)
        if not champ: return
        self.current_champ = champ
        
        act = activity_service.get(champ.activity_id) if champ.activity_id else None
        act_name = activity_service.get_localized_name(act) if act else "—"
        self.title_label.setText(f"{champ.name} · {act_name}")
        
        self._rows = championship_service.get_participants(self.champ_id)
        
        # Calculate KPIs
        p_count = len(self._rows)
        golds = sum(1 for p in self._rows if p.get("result") == "gold")
        silvers = sum(1 for p in self._rows if p.get("result") == "silver")
        bronzes = sum(1 for p in self._rows if p.get("result") == "bronze")
        
        self.kpi_participants.set_value(str(p_count))
        self.kpi_gold.set_value(str(golds))
        self.kpi_silver.set_value(str(silvers))
        self.kpi_bronze.set_value(str(bronzes))
        
        # Fee KPI (per player and expected total)
        fee = champ.entry_fee or 0
        expected_total = fee * p_count
        self.kpi_fee.set_value(f"{fee:,.0f} EGP")
        self.kpi_fee.set_subtitle(t("champ.detail.kpi.fee_total", total=f"{expected_total:,.0f} EGP"))

        # Populate Table
        self.table.setRowCount(len(self._rows))
        for i, p in enumerate(self._rows):
            # 1. Player Name
            name_item = QTableWidgetItem(p["full_name"])
            name_item.setData(Qt.ItemDataRole.UserRole, p["id"])
            self.table.setItem(i, 0, name_item)
            
            # 2. Weight
            weight = p.get("weight_kg")
            self.table.setItem(i, 1, QTableWidgetItem(f"{weight} kg" if weight else "—"))
            
            # 3. Belt
            belt = p.get("belt") or "—"
            if belt != "—": belt = t(f"belt.{belt.lower()}")
            self.table.setItem(i, 2, QTableWidgetItem(belt))
            
            # 4. Result (THE FIX: Pass as a Dict for the Delegate!)
            result = p.get("result")
            result_item = QTableWidgetItem()
            
            if result:
                # The delegate needs "text" and "kind"
                result_item.setData(
                    Qt.ItemDataRole.UserRole, 
                    {"text": t(f"result.{result}"), "kind": result}
                )
            else:
                result_item.setText("—")
                result_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # Passing a None kind tells the delegate to just draw plain text
                result_item.setData(Qt.ItemDataRole.UserRole, None) 

            self.table.setItem(i, 3, result_item)

        # --- MOVED OUTSIDE THE LOOP ---
        # Apply the delegate and column widths ONCE, not per row.
        self.table.setColumnWidth(3, 110)
        self._pill_delegate = PillDelegate(self.table)
        self.table.setItemDelegateForColumn(3, self._pill_delegate)
        self.table.verticalHeader().setDefaultSectionSize(36)

        # Toggle Empty State
        if self._rows:
            self.table.show()
            self.empty_label.hide()
        else:
            self.table.hide()
            self.empty_label.show()
            
        self._update_actions()

    def _selected_participant(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows: return None
        idx = rows[0].row()
        if 0 <= idx < len(self._rows): return self._rows[idx]
        return None

    def _update_actions(self):
        self.remove_btn.setEnabled(self._selected_participant() is not None)

    def _on_back(self):
        if self.on_back: self.on_back()

    def _on_edit(self):
        dlg = ChampionshipFormDialog(self.current_champ, parent=self)
        if dlg.exec():
            QTimer.singleShot(0, self._refresh_deferred)

    def _on_delete(self):
        if ask(self, t("champ.confirm.delete_champ_title"), t("champ.confirm.delete_champ_msg", name=self.current_champ.name)):
            championships_repo.archive_championship(self.champ_id)
            self._on_back()

    def _on_assign(self):
        existing_ids = [p["player_id"] for p in self._rows]
        dlg = AssignPlayerDialog(self.champ_id, existing_ids, parent=self)
        if dlg.exec():
            QTimer.singleShot(0, self._refresh_deferred)

    def _on_remove(self):
        p = self._selected_participant()
        if not p:
            return
        if not ask(self, t("champ.confirm.remove_title"),
                   t("champ.confirm.remove_msg", name=p["full_name"])):
            return

        # Delete the DB row immediately (this is fast — a single DELETE),
        # but defer the visual refresh by one event-loop tick so the
        # confirmation dialog has fully closed and its frame is gone
        # before we rebuild the table and KPI strip. Without this, the
        # OS paints a white frame during the rebuild.
        championships_repo.remove_participant(p["id"])
        QTimer.singleShot(0, self._refresh_deferred)

    def _refresh_deferred(self):
        """Refresh with paint updates frozen to avoid the white-flash bug."""
        self.setUpdatesEnabled(False)
        try:
            self.refresh()
        finally:
            self.setUpdatesEnabled(True)
            self.update()

    def _on_edit_result(self, item):
        p = self._selected_participant()
        if not p: return
        
        # Open the custom themed dialog instead of QInputDialog
        current_res = p.get("result")
        dlg = EditResultDialog(current_res, p["full_name"], parent=self)
        
        if dlg.exec() == dlg.DialogCode.Accepted:
            new_res = dlg.get_result()
            
            from models.championship import ChampionshipParticipant
            obj = championships_repo.get_participant(p["id"])
            if obj:
                obj.result = new_res
                championships_repo.update_participant(obj)
                QTimer.singleShot(0, self._refresh_deferred)

    def _on_export(self):
        if not self._rows:
            info(self, t("audit.export.empty_title"), t("audit.export.empty_body"))
            return
            
        path, _ = QFileDialog.getSaveFileName(
            self, t("champ.detail.export_title"),
            f"championship_{self.champ_id}_{date.today().isoformat()}.csv",
            "CSV (*.csv)"
        )
        if not path: return
        
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow([t("champ.col.player"), t("champ.col.belt"), t("champ.col.weight"), t("champ.col.result")])
                for p in self._rows:
                    w.writerow([
                        p["full_name"],
                        p.get("belt", ""),
                        p.get("weight_kg", ""),
                        p.get("result", "")
                    ])
            info(self, t("msg.save"), t("champ.detail.export_done", path=path))
        except Exception as e:
            warn(self, t("msg.error"), str(e))