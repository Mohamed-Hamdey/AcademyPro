"""
Activity Detail Screen — v6 Dashboard (Phases 1-3).
"""
import os
import sys
from datetime import date
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QFrame, QButtonGroup,QTableWidgetItem,QSizePolicy,QTableWidget
)
from qtpy.QtCore import Qt, QTimer, QSettings
from qtpy.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import activity_service
from ui.table_helpers import make_standard_table
from ui.components import SectionCard, KpiCard, ComboBarChart, EmptyState, Pill
from ui.theme import make_warning, theme, ThemedWidget, make_secondary, make_segment, make_danger
from ui.design import SPACING
from ui.i18n import t
from ui.message_box import info, warn, ask
from ui.dialogs.activity_form_dialog import ActivityFormDialog
from ui.utils import get_date_range


class ActivityDetailScreen(ThemedWidget, QWidget):
    def __init__(self, activity_id, on_back=None, parent=None):
        QWidget.__init__(self, parent)
        self.activity_id = activity_id
        self.on_back = on_back
        self._active_players = []
        self._current_range = "this_month"
        
        self._build_ui()
        self._init_theme()
        
        # Restore saved period
        s = QSettings("MembershipSystem", "app")
        saved_range = s.value("activity_detail/period", "this_month")
        idx = self._period_group.buttons().index(self._range_buttons.get(saved_range, self._btn_month))
        if idx >= 0:
            self._period_group.buttons()[idx].setChecked(True)
            self._current_range = saved_range


    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, "_loaded") or not self._loaded:
            self._loaded = True
            QTimer.singleShot(0, self.refresh)
    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["md"])

        # --- Header ---
        header = QHBoxLayout()
        
        title_col = QVBoxLayout()
        title_col.setSpacing(6)
        
        title_row = QHBoxLayout()
        self.title_label = QLabel()
        title_row.setSpacing(SPACING["sm"])

        self.title_label.setObjectName("pageTitle")
        self.status_pill = Pill("", "success")
        self.status_pill.hide()
        
        title_row.addWidget(self.title_label)
        title_row.addWidget(self.status_pill)
        title_row.addStretch()
        
        self.subtitle_label = QLabel()
        self.subtitle_label.setStyleSheet(f"color: {theme().color('text_secondary')}; font-size: 13px;")
        
        title_col.addLayout(title_row)
        title_col.addWidget(self.subtitle_label)
        header.addLayout(title_col, stretch=1)
        header.addStretch()

        self.edit_btn = QPushButton(t("champ.detail.edit"))
        make_secondary(self.edit_btn)
        self.edit_btn.clicked.connect(self._on_edit)
        header.addWidget(self.edit_btn)
        
        # --- NEW: Deactivate and Delete buttons ---
        self.toggle_btn = QPushButton(t("activities.action.deactivate"))
        make_warning(self.toggle_btn)
        self.toggle_btn.clicked.connect(self._on_toggle_active)
        header.addWidget(self.toggle_btn)

        self.delete_btn = QPushButton(t("activities.action.delete"))
        make_danger(self.delete_btn)
        self.delete_btn.clicked.connect(self._on_delete)
        header.addWidget(self.delete_btn)
        # -----------------------------------------

        self.back_btn = QPushButton(t("activities.detail.back"))
        self.back_btn.clicked.connect(self._on_back)
        header.addWidget(self.back_btn)
        root.addLayout(header)

        # --- Period Selector ---
        period_row = QHBoxLayout()
        period_row.setSpacing(SPACING["sm"])
        
        self._period_group = QButtonGroup(self)
        self._period_group.setExclusive(True)
        
        self._btn_month = QPushButton(t("activities.period.this_month"))
        self._btn_30d = QPushButton(t("activities.period.last_30_days"))
        self._btn_3m = QPushButton(t("activities.period.last_3_months"))
        self._btn_year = QPushButton(t("activities.period.this_year"))
        
        self._range_buttons = {
            "this_month": self._btn_month,
            "last_30_days": self._btn_30d,
            "last_3_months": self._btn_3m,
            "this_year": self._btn_year,
        }
        
        for btn in self._range_buttons.values():
            btn.setCheckable(True)
            make_segment(btn)
            self._period_group.addButton(btn)
            btn.clicked.connect(self._on_period_changed)
            period_row.addWidget(btn)
            
        self._btn_month.setChecked(True)
        period_row.addStretch()
        root.addLayout(period_row)

        # --- Scrollable Content ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["lg"])

        # --- KPI Strip ---
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(SPACING["sm"])
        
        self.kpi_players = KpiCard(t("activities.detail.kpi.players"), "0")
        self.kpi_revenue = KpiCard(t("activities.detail.kpi.revenue"), "0 EGP", value_color="success")
        self.kpi_attendance = KpiCard(t("activities.detail.kpi.attendance"), "0")
        self.kpi_needs_attn = KpiCard(t("activities.detail.kpi.needs_attention"), "0", value_color="danger")
        
        for kpi in (self.kpi_players, self.kpi_revenue, self.kpi_attendance, self.kpi_needs_attn):
            kpi_row.addWidget(kpi, stretch=1)
        layout.addLayout(kpi_row)

        # --- Charts Row ---
        charts_row = QHBoxLayout()
        charts_row.setSpacing(SPACING["lg"])

        # 1. Revenue Chart
        self.revenue_card = SectionCard(title=t("activities.detail.chart.revenue"))
        self.revenue_chart = ComboBarChart(
            height=160,
            series_labels=["Revenue"],
            series_colors=["success"]
        )
        self.revenue_card.body.addWidget(self.revenue_chart)
        self.revenue_empty = EmptyState(icon="💰", message=t("activities.detail.no_revenue"))
        self.revenue_empty.hide()
        self.revenue_card.body.addWidget(self.revenue_empty)
        charts_row.addWidget(self.revenue_card, stretch=1)

        # 2. Attendance Chart
        self.attendance_card = SectionCard(title=t("activities.detail.chart.attendance"))
        self.attendance_chart = ComboBarChart(
            height=160,
            series_labels=["Attendance"],
            series_colors=["primary"]
        )
        self.attendance_card.body.addWidget(self.attendance_chart)
        self.attendance_empty = EmptyState(icon="👥", message=t("activities.detail.no_attendance"))
        self.attendance_empty.hide()
        self.attendance_card.body.addWidget(self.attendance_empty)
        charts_row.addWidget(self.attendance_card, stretch=1)

        layout.addLayout(charts_row)

        # --- Active Players Table (Phase 3 basic version) ---
        self.table_card = SectionCard(title=t("activities.detail.active_players"))
        self.table_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table = make_standard_table(
            headers=[
                t("champ.col.player"),
                t("detail.sub.col.plan"),
                t("detail.sub.col.sessions"),
                t("detail.sub.col.expires"),
            ],
            column_modes=["stretch", "resize", "resize", "resize"],
            parent=self,
        )
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table_card.body.addWidget(self.table, stretch=1)

        self.empty_label = EmptyState(icon="👥", message=t("activities.detail.no_players"))
        self.empty_label.hide()
        self.table_card.body.addWidget(self.empty_label)

        layout.addWidget(self.table_card, stretch=1)
        layout.addStretch(0)

        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    # ---------- theming ----------

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
        )

    # ---------- period handling ----------

    def _on_period_changed(self):
        for key, btn in self._range_buttons.items():
            if btn.isChecked():
                self._current_range = key
                QSettings("MembershipSystem", "app").setValue("activity_detail/period", key)
                break
        QTimer.singleShot(0, self.refresh)

    # ---------- data ----------

    def refresh(self):
        act = activity_service.get(self.activity_id)
        if not act:
            return
    
        self.current_activity = act 

        # 1. Update Header
        self.title_label.setText(act.name)
        
        if act.active:
            self.status_pill.set_status(t("activities.status.active"), "success")
            self.toggle_btn.setText(t("activities.action.deactivate")) # <--- ADD THIS
            make_warning(self.toggle_btn)                              # <--- ADD THIS
        else:
            self.status_pill.set_status(t("activities.status.inactive"), "warning")
            self.toggle_btn.setText(t("activities.action.reactivate")) # <--- ADD THIS
            make_warning(self.toggle_btn)                              # <--- ADD THIS
        self.status_pill.show()

        days_str = ", ".join(t(f"weekday.{d.lower()}") for d in act.default_days)
        self.subtitle_label.setText(days_str or "—")

        # 2. Load KPIs
        date_from, date_to = get_date_range(self._current_range)
        kpis = activity_service.get_kpis(self.activity_id, date_from, date_to)
        
        self.kpi_players.set_value(str(kpis["active_players"]))
        self.kpi_revenue.set_value(f"{kpis['revenue']:,.0f} EGP")
        self.kpi_attendance.set_value(str(kpis["attendance"]))
        
        # Needs attention = expiring + low sessions
        needs_attn = kpis["expiring_soon"] + kpis["low_sessions"]
        self.kpi_needs_attn.set_value(str(needs_attn))

        # 3. Load Charts
        charts_data = activity_service.get_charts_data(self.activity_id)
        
        # -- Revenue Chart --
        rev_slots = []
        has_rev = False
        for m in charts_data["revenue"]:
            if m["total"] > 0:
                has_rev = True
            rev_slots.append({
                "label": m["month_label"],
                "key": m["month_label"],
                "values": [m["total"]],
                "highlight": False
            })
            
        if has_rev:
            self.revenue_chart.set_data(rev_slots)
            self.revenue_chart.show()
            self.revenue_empty.hide()
        else:
            self.revenue_chart.hide()
            self.revenue_empty.show()

        # -- Attendance Chart --
        att_slots = []
        has_att = False
        for w in charts_data["attendance"]:
            if w["count"] > 0:
                has_att = True
            att_slots.append({
                "label": w["week_label"],
                "key": w["week_label"],
                "values": [w["count"]],
                "highlight": False
            })
            
        if has_att:
            self.attendance_chart.set_data(att_slots)
            self.attendance_chart.show()
            self.attendance_empty.hide()
        else:
            self.attendance_chart.hide()
            self.attendance_empty.show()

        # 4. Load Players Table (basic for Phase 3)
        self._load_players_table()

    def _load_players_table(self):
        from db.database import get_connection
        from config.config_loader import get_plan_label
        
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT s.*, p.full_name 
                FROM subscriptions s
                JOIN players p ON p.player_id = s.player_id
                WHERE s.activity_id = ? AND s.status = 'active' AND s.archived_at IS NULL
                ORDER BY s.sessions_remaining ASC, p.full_name
                """,
                (self.activity_id,)
            ).fetchall()
            self._active_players = [dict(r) for r in rows]
        finally:
            conn.close()

        players = self._active_players
        if not players:
            self.table.hide()
            self.empty_label.show()
            return

        self.table.show()
        self.empty_label.hide()
        self.table.setRowCount(len(players))

        for i, p in enumerate(players):
            name_item = QTableWidgetItem(p["full_name"])
            name_item.setData(Qt.ItemDataRole.UserRole, p["player_id"])
            self.table.setItem(i, 0, name_item)

            plan = get_plan_label(p["plan_type"]) if p["plan_type"] else t("detail.sub.custom")
            self.table.setItem(i, 1, QTableWidgetItem(plan))

            sess = QTableWidgetItem(f"{p['sessions_remaining']} / {p['sessions_total']}")
            sess.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, sess)

            self.table.setItem(i, 3, QTableWidgetItem(p["expiry_date"]))

    # ---------- actions ----------

    def _on_back(self):
        if self.on_back:
            self.on_back()

    def _on_edit(self):
        act = activity_service.get(self.activity_id)
        if not act:
            return
        dlg = ActivityFormDialog(activity=act, parent=self)
        if dlg.exec():
            QTimer.singleShot(0, self.refresh)
            
            
    def _on_toggle_active(self):
        act = activity_service.get(self.activity_id)
        if not act:
            return

        if act.active:
            refs = activity_service.count_references(self.activity_id)
            msg_key = "activities.confirm.deactivate_with_refs" if refs > 0 else "activities.confirm.deactivate"
            if not ask(self, t("activities.confirm.title"), t(msg_key, name=act.name, count=refs)):
                return
            activity_service.deactivate(self.activity_id)
        else:
            activity_service.reactivate(self.activity_id)

        QTimer.singleShot(0, self.refresh)

    def _on_delete(self):
        act = activity_service.get(self.activity_id)
        if not act:
            return
        if not ask(self, t("activities.confirm.delete_title"), t("activities.confirm.delete_msg", name=act.name)):
            return
        
        try:
            from repositories import activities_repo
            activities_repo.archive(self.activity_id)
        except Exception as e:
            warn(self, t("activities.confirm.title"), str(e))
            return
            
        # Instead of refreshing, go back to the list because the activity is archived
        if self.on_back:
            self.on_back()