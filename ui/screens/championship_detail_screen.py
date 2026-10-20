"""
Championship Detail Screen (Master-Detail).
"""
import os
import sys
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidgetItem, QInputDialog,
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import championships_repo
from services import championship_service
from ui.dialogs.assign_player_dialog import AssignPlayerDialog
from ui.dialogs.championship_form_dialog import ChampionshipFormDialog
from ui.table_helpers import make_standard_table
from ui.components import SectionCard, KpiCard
from ui.theme import theme, ThemedWidget, make_danger, make_secondary
from ui.design import SPACING
from ui.i18n import t
from ui.message_box import info, ask


class ChampionshipDetailScreen(ThemedWidget, QWidget):
    def __init__(self, championship_id, on_back=None, parent=None):
        QWidget.__init__(self, parent)
        self.champ_id = championship_id
        self.on_back = on_back
        self._rows = []
        self._build_ui()
        self.refresh()
        self._init_theme()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        # --- Header row: Title | Edit | Delete | Back ---
        header = QHBoxLayout()
        self.title_label = QLabel()
        header.addWidget(self.title_label)
        header.addStretch()

        self.edit_btn = QPushButton(t("champ.detail.edit"))
        make_secondary(self.edit_btn)
        self.edit_btn.clicked.connect(self._on_edit)
        header.addWidget(self.edit_btn)

        self.delete_btn = QPushButton(t("champ.detail.delete"))
        make_danger(self.delete_btn)
        self.delete_btn.clicked.connect(self._on_delete)
        header.addWidget(self.delete_btn)

        self.back_btn = QPushButton(t("champ.detail.back"))
        self.back_btn.clicked.connect(self._on_back)
        header.addWidget(self.back_btn)

        root.addLayout(header)

        # --- KPI strip ---
        kpi_row = QHBoxLayout()
        self.participants_kpi = KpiCard(
            t("champ.detail.participants"), "0", value_color="primary"
        )
        self.fees_kpi = KpiCard(
            t("champ.detail.total_fees"), "0 EGP", value_color="success"
        )
        kpi_row.addWidget(self.participants_kpi, stretch=1)
        kpi_row.addWidget(self.fees_kpi, stretch=1)
        root.addLayout(kpi_row)

        # --- Participant table card ---
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

        # --- Action row ---
        actions = QHBoxLayout()

        self.remove_btn = QPushButton(t("champ.detail.remove"))
        make_danger(self.remove_btn)
        self.remove_btn.clicked.connect(self._on_remove)
        self.remove_btn.setEnabled(False)

        self.edit_result_btn = QPushButton(t("champ.detail.edit_result"))
        make_secondary(self.edit_result_btn)
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
        self.title_label.setStyleSheet(
            f"font-size: 24px; font-weight: 700; color: {tm.color('text')};"
        )
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

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def refresh(self):
        champ = championships_repo.get_championship(self.champ_id)
        if not champ:
            return

        self.title_label.setText(champ.name)
        self.current_champ = champ
        
        # --- NEW: عرض النشاط المرتبط بالبطولة ---
        from services import activity_service
        act = activity_service.get(champ.activity_id) if champ.activity_id else None
        act_name = activity_service.get_localized_name(act) if act else "—"
        self.title_label.setText(f"{champ.name}\n{t('champ.detail.activity', activity=act_name)}")
        # -----------------------------------------

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

            weight = p.get("weight_kg")
            self.table.setItem(
                i, 1,
                QTableWidgetItem(f"{weight} kg" if weight else "—"),
            )

            self.table.setItem(i, 2, QTableWidgetItem(self._fmt_belt(p.get("belt"))))
            self.table.setItem(i, 3, QTableWidgetItem(self._fmt_result(p.get("result"))))

        self._update_actions()

    # ---------- display helpers ----------

    @staticmethod
    def _fmt_belt(raw):
        """
        Belt stored as a lowercase key ('white'..'black') since T5.
        Falls back to the raw value if unknown (legacy safety).
        """
        if not raw:
            return "—"
        key = str(raw).strip().lower()
        known = {"white", "yellow", "orange", "green", "blue", "brown", "black"}
        if key in known:
            translated = t(f"belt.{key}")
            # i18n helper may return the key itself on miss — fall back to raw.
            return translated if translated and translated != f"belt.{key}" else raw
        return raw

    @staticmethod
    def _fmt_result(raw):
        """Same idea for result ('gold'|'silver'|'bronze'|'participant')."""
        if not raw:
            return "—"
        key = str(raw).strip().lower()
        known = {"gold", "silver", "bronze", "participant"}
        if key in known:
            translated = t(f"result.{key}")
            return translated if translated and translated != f"result.{key}" else raw
        return raw

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _selected_participant(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._rows):
            return None
        return self._rows[idx]

    def _update_actions(self):
        has = self._selected_participant() is not None
        self.remove_btn.setEnabled(has)
        self.edit_result_btn.setEnabled(has)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_back(self):
        if self.on_back:
            self.on_back()

    def _on_edit(self):
        # Snapshot participant count so we can detect the repo's cascade
        # auto-removal (activity change → players without a matching sub
        # are deleted by update_championship()).
        before_count = len(self._rows)

        dlg = ChampionshipFormDialog(self.current_champ, parent=self)
        if not dlg.exec():
            return

        self.refresh()
        after_count = len(self._rows)

        if after_count < before_count:
            info(
                self,
                t("champ.detail.cascade.title"),
                t("champ.detail.cascade.body", n=before_count - after_count),
            )

    def _on_delete(self):
        """
        Soft-delete → archive the championship → return to list.
        Never calls delete_championship() here; that is reserved for
        'delete forever' from the Recycle Bin.
        """
        champ = getattr(self, "current_champ", None)
        if champ is None:
            return
        if not ask(
            self,
            t("champ.confirm.delete_title"),
            t("champ.confirm.delete_msg", name=champ.name),
        ):
            return
        try:
            championships_repo.archive_championship(champ.championship_id)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to archive championship %s", champ.championship_id
            )
            return
        self._on_back()

    def _on_assign(self):
        existing_ids = [p["player_id"] for p in self._rows]
        dlg = AssignPlayerDialog(self.champ_id, existing_ids, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_remove(self):
        p = self._selected_participant()
        if p and ask(
            self,
            t("champ.confirm.remove_title"),
            t("champ.confirm.remove_msg", name=p["full_name"]),
        ):
            championships_repo.remove_participant(p["id"])
            
            # --- NEW AUDIT CALL ---
            try:
                from services import audit_service
                audit_service.record(
                    "championship.remove_participant",
                    target_type="championship",
                    target_id=self.champ_id,
                    details={"player_name": p["full_name"]},
                )
            except Exception:
                pass
            # ----------------------
            
            self.refresh()

    def _on_edit_result(self):
        p = self._selected_participant()
        if not p:
            return

        # Present translated labels, but store the KEY.
        choices = [
            ("gold",        t("result.gold")),
            ("silver",      t("result.silver")),
            ("bronze",      t("result.bronze")),
            ("participant", t("result.participant")),
            (None,          t("result.none")),
        ]
        labels = [label for _, label in choices]

        current_key = str(p.get("result") or "").strip().lower()
        current_idx = 0
        for i, (key, _) in enumerate(choices):
            if key == current_key:
                current_idx = i
                break

        chosen_label, ok = QInputDialog.getItem(
            self,
            t("champ.detail.edit_result"),
            t("champ.col.result"),
            labels,
            current_idx,
            False,
        )
        if not ok or not chosen_label:
            return

        # Map the chosen label back to its key.
        chosen_key = None
        for key, label in choices:
            if label == chosen_label:
                chosen_key = key
                break

        from models.championship import ChampionshipParticipant
        obj = championships_repo.get_participant(p["id"])
        if obj is None:
            return
        obj.result = chosen_key
        championships_repo.update_participant(obj)
        
        # --- NEW AUDIT CALL ---
        try:
            from services import audit_service
            audit_service.record(
                "championship.edit_result",
                target_type="championship",
                target_id=self.champ_id,
                details={"player_name": p["full_name"], "result": chosen_key},
            )
        except Exception:
            pass
        # ----------------------
        
        self.refresh()