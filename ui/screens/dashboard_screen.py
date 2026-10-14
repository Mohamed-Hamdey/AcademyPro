"""
Manager dashboard — daily + monthly views.
"""

import os
import sys
from datetime import date, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QScrollArea, QFrame, QTabWidget, QDateEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import dashboard_service, activity_service
from ui.components import (
    SectionCard, KpiCard, Toolbar, BarList, ComboBarChart, EmptyState,
)
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui import i18n


MONTH_KEYS = [
    "month.january", "month.february", "month.march", "month.april",
    "month.may", "month.june", "month.july", "month.august",
    "month.september", "month.october", "month.november", "month.december",
]

WEEKDAY_KEYS = {
    0: "weekday.monday",
    1: "weekday.tuesday",
    2: "weekday.wednesday",
    3: "weekday.thursday",
    4: "weekday.friday",
    5: "weekday.saturday",
    6: "weekday.sunday",
}

BAR_COLOR_CYCLE = ["primary", "success", "warning", "info", "danger"]


class DashboardScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._selected_date = date.today()
        self._summary = None
        self._month_summary = None
        self._week_rows = []
        self._sport_filter_id = None
        self._method_filter = None
        self._build_ui()
        self.refresh()
        self._init_theme()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        self.tabs = QTabWidget()

        daily = QWidget()
        daily_root = QVBoxLayout(daily)
        daily_root.setContentsMargins(0, SPACING["lg"], 0, 0)
        daily_root.setSpacing(SPACING["lg"])
        self.tabs.addTab(daily, t("dash.tab.daily"))
        self._build_daily_page(daily_root)

        monthly = QWidget()
        monthly_root = QVBoxLayout(monthly)
        monthly_root.setContentsMargins(0, SPACING["lg"], 0, 0)
        monthly_root.setSpacing(SPACING["lg"])
        self.tabs.addTab(monthly, t("dash.tab.monthly"))
        self._build_monthly_page(monthly_root)

        root.addWidget(self.tabs, stretch=1)

    # ---------- Daily page ----------

    def _build_daily_page(self, root):
        # Toolbar: date navigation
        self.toolbar = Toolbar()

        self.prev_button = QPushButton("◀")
        make_secondary(self.prev_button)
        self.prev_button.setFixedWidth(42)
        self.prev_button.clicked.connect(self._on_prev_day)

        self.next_button = QPushButton("▶")
        make_secondary(self.next_button)
        self.next_button.setFixedWidth(42)
        self.next_button.clicked.connect(self._on_next_day)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setMinimumWidth(140)
        self.date_input.dateChanged.connect(self._on_date_changed)

        self.today_button = QPushButton(t("dash.jump_today"))
        make_secondary(self.today_button)
        self.today_button.clicked.connect(self._on_jump_today)

        self.toolbar.add_leading(QLabel(t("dash.date_label")))
        self.toolbar.add_leading(self.prev_button)
        self.toolbar.add_leading(self.date_input)
        self.toolbar.add_leading(self.next_button)
        self.toolbar.add_leading(self.today_button)

        root.addWidget(self.toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(SPACING["lg"])

        # KPI row (with comparison badges)
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(SPACING["md"])
        self.rev_card = KpiCard(t("dash.kpi.revenue"), "0")
        self.exp_card = KpiCard(t("dash.kpi.expenses"), "0")
        self.net_card = KpiCard(t("dash.kpi.net"), "0")
        self.att_card = KpiCard(t("dash.kpi.attendance"), "0")
        for c in (self.rev_card, self.exp_card, self.net_card, self.att_card):
            kpi_row.addWidget(c, stretch=1)
        body.addLayout(kpi_row)

        # Comparison badges row
        self.badges_row = QHBoxLayout()
        self.badges_row.setSpacing(SPACING["md"])
        self._badge_labels = {}
        for key in ("revenue", "expenses", "net", "attendance"):
            wrap = QWidget()
            wl = QVBoxLayout(wrap)
            wl.setContentsMargins(6, 0, 6, 0)
            wl.setSpacing(2)
            lbl_y = QLabel()
            lbl_wd = QLabel()
            lbl_avg = QLabel()
            self._badge_labels[key] = (lbl_y, lbl_wd, lbl_avg)
            wl.addWidget(lbl_y)
            wl.addWidget(lbl_wd)
            wl.addWidget(lbl_avg)
            self.badges_row.addWidget(wrap, stretch=1)
        body.addLayout(self.badges_row)

        # Reconciliation strip
        self.recon_card = SectionCard(title=t("dash.reconcile.title"))
        self.recon_layout = QHBoxLayout()
        self.recon_layout.setSpacing(SPACING["lg"])
        self._recon_labels = {}
        for key in ("payments", "payers", "attendance", "cash", "transfer"):
            lbl = QLabel()
            self._recon_labels[key] = lbl
            self.recon_layout.addWidget(lbl)
        self.recon_layout.addStretch()
        self.recon_card.body.addLayout(self.recon_layout)
        body.addWidget(self.recon_card)

        # Payments table card
        self.payments_card = SectionCard(title=t("dash.payments"))

        # Filters row
        filters = QHBoxLayout()
        filters.setSpacing(SPACING["sm"])

        self.sport_filter = QComboBox()
        self.sport_filter.addItem(t("dash.payments.filter.all_sports"), None)
        for act in activity_service.list_active():
            name = (act.name_ar if i18n.current_language() == "ar"
                    else act.name_en)
            self.sport_filter.addItem(name, act.activity_id)
        self.sport_filter.currentIndexChanged.connect(self._on_filters_changed)

        self.method_filter = QComboBox()
        self.method_filter.addItem(t("dash.payments.filter.all_methods"), None)
        self.method_filter.addItem(t("dash.payments.method.cash"), "cash")
        self.method_filter.addItem(t("dash.payments.method.transfer"), "transfer")
        self.method_filter.addItem(t("dash.payments.method.other"), "other")
        self.method_filter.currentIndexChanged.connect(self._on_filters_changed)

        filters.addWidget(QLabel(t("dash.payments.filter.sport")))
        filters.addWidget(self.sport_filter)
        filters.addWidget(QLabel(t("dash.payments.filter.method")))
        filters.addWidget(self.method_filter)
        filters.addStretch()
        self.payments_card.body.addLayout(filters)

        # Table
        self.payments_table = QTableWidget(0, 6)
        self.payments_table.setHorizontalHeaderLabels([
            t("dash.payments.col.time"),
            t("dash.payments.col.player"),
            t("dash.payments.col.sport"),
            t("dash.payments.col.amount"),
            t("dash.payments.col.method"),
            t("dash.payments.col.note"),
        ])
        hdr = self.payments_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.payments_table.verticalHeader().setVisible(False)
        self.payments_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.payments_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.payments_table.setAlternatingRowColors(True)
        self.payments_table.setShowGrid(False)
        self.payments_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.payments_table.setMinimumHeight(220)
        self.payments_table.setSortingEnabled(True)
        self.payments_card.body.addWidget(self.payments_table)

        # Total row
        self.payments_total_label = QLabel()
        self.payments_total_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.payments_card.body.addWidget(self.payments_total_label)

        self.payments_card.hide()  # will show if there are rows
        body.addWidget(self.payments_card)

        # Last 7 days: charts + table
        self.week_card = SectionCard(title=t("dash.week_table"))
        self.week_hint = QLabel(t("dash.week_table_hint"))
        self.week_hint.setWordWrap(True)
        self.week_card.body.addWidget(self.week_hint)

        # Charts: combined revenue + expenses
        self.combo_chart = ComboBarChart(
            height=130,
            series_labels=[
                t("dash.chart.revenue"),
                t("dash.chart.expenses"),
            ],
            series_colors=["success", "danger"],
        )
        self.combo_chart.slotClicked.connect(self._on_chart_bar_clicked)
        self.week_card.body.addWidget(self.combo_chart)

        # 7-day table
        self.week_table = QTableWidget(0, 5)
        self.week_table.setHorizontalHeaderLabels([
            t("dash.week.col.day"),
            t("dash.week.col.date"),
            t("dash.week.col.attendance"),
            t("dash.week.col.revenue"),
            t("dash.week.col.signups"),
        ])
        whdr = self.week_table.horizontalHeader()
        whdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        whdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        whdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        whdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        whdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.week_table.verticalHeader().setVisible(False)
        self.week_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.week_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.week_table.setAlternatingRowColors(True)
        self.week_table.setShowGrid(False)
        self.week_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.week_table.setMinimumHeight(220)
        self.week_table.cellClicked.connect(self._on_week_row_clicked)
        self.week_table.setCursor(Qt.CursorShape.PointingHandCursor)
        self.week_card.body.addWidget(self.week_table)
        body.addWidget(self.week_card)

        body.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    # ---------- Monthly page ----------

    def _build_monthly_page(self, root):
        self.month_toolbar = Toolbar()

        self.month_selector = QComboBox()
        today = date.today()
        self._month_options = []
        for i in range(11, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            self._month_options.append((y, m))
            self.month_selector.addItem(f"{t(MONTH_KEYS[m-1])} {y}")
        self.month_selector.setCurrentIndex(len(self._month_options) - 1)
        self.month_selector.currentIndexChanged.connect(self._on_month_changed)

        self.month_toolbar.add_leading(self.month_selector)
        root.addWidget(self.month_toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(SPACING["lg"])

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(SPACING["md"])
        self.m_rev_card = KpiCard(t("dash.kpi.revenue"), "0")
        self.m_exp_card = KpiCard(t("dash.kpi.expenses"), "0")
        self.m_net_card = KpiCard(t("dash.kpi.net"), "0")
        self.m_att_card = KpiCard(t("dash.kpi.attendance"), "0")
        for c in (self.m_rev_card, self.m_exp_card, self.m_net_card, self.m_att_card):
            kpi_row.addWidget(c, stretch=1)
        body.addLayout(kpi_row)

        row2 = QHBoxLayout()
        row2.setSpacing(SPACING["lg"])

        self.m_by_act_card = SectionCard(title=t("dash.month.by_activity"))
        self.m_by_act_bars = BarList()
        self.m_by_act_card.body.addWidget(self.m_by_act_bars)
        self.m_by_act_empty = EmptyState(
            icon="💰",
            message=t("dash.month.no_revenue"),
        )
        self.m_by_act_empty.hide()
        self.m_by_act_card.body.addWidget(self.m_by_act_empty)
        row2.addWidget(self.m_by_act_card, stretch=1)

        self.m_by_cat_card = SectionCard(title=t("dash.month.expenses_by_category"))
        self.m_by_cat_bars = BarList()
        self.m_by_cat_card.body.addWidget(self.m_by_cat_bars)
        row2.addWidget(self.m_by_cat_card, stretch=1)

        body.addLayout(row2)

        self.m_by_method_card = SectionCard(title=t("dash.month.by_method"))
        self.m_by_method_bars = BarList()
        self.m_by_method_card.body.addWidget(self.m_by_method_bars)
        body.addWidget(self.m_by_method_card)

        body.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    # ---------- theming ----------

    def restyle(self):
        tm = theme()

        self._style_kpi(self.rev_card,   tm.color("success"))
        self._style_kpi(self.exp_card,   tm.color("danger"))
        self._style_kpi(self.net_card,   tm.color("primary"))
        self._style_kpi(self.att_card,   tm.color("text"))
        self._style_kpi(self.m_rev_card, tm.color("success"))
        self._style_kpi(self.m_exp_card, tm.color("danger"))
        self._style_kpi(self.m_net_card, tm.color("primary"))
        self._style_kpi(self.m_att_card, tm.color("text"))

        self.week_hint.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"  padding: 0 0 6px 0;"
            f"}}"
        )
        self.payments_total_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 14px;"
            f"  font-weight: 700;"
            f"  padding-top: 6px;"
            f"}}"
        )

        if self._summary is not None:
            self._render_day()
        if self._month_summary is not None:
            self._render_month()

    @staticmethod
    def _style_kpi(kpi, color):
        kpi.value_label.setStyleSheet(
            f"QLabel#kpiValue {{"
            f"  color: {color};"
            f"  background-color: transparent;"
            f"  font-size: 22px;"
            f"  font-weight: 700;"
            f"}}"
        )

    # ---------- date navigation ----------

    def _on_prev_day(self):
        self._selected_date -= timedelta(days=1)
        self._sync_date_input()
        self.refresh()

    def _on_next_day(self):
        self._selected_date += timedelta(days=1)
        self._sync_date_input()
        self.refresh()

    def _on_jump_today(self):
        self._selected_date = date.today()
        self._sync_date_input()
        self.refresh()

    def _on_date_changed(self, qd: QDate):
        new_date = date(qd.year(), qd.month(), qd.day())
        if new_date != self._selected_date:
            self._selected_date = new_date
            self.refresh()

    def _sync_date_input(self):
        self.date_input.blockSignals(True)
        self.date_input.setDate(QDate(
            self._selected_date.year,
            self._selected_date.month,
            self._selected_date.day,
        ))
        self.date_input.blockSignals(False)

    def _on_month_changed(self, _idx):
        self._refresh_month()

    def _on_filters_changed(self, _idx):
        self._sport_filter_id = self.sport_filter.currentData()
        self._method_filter = self.method_filter.currentData()
        self._render_payments()

    # ---------- data ----------

    def refresh(self):
        self._summary = dashboard_service.day_summary(self._selected_date)
        self._render_day()
        self._refresh_month()

    def _refresh_month(self):
        y, m = self._month_options[self.month_selector.currentIndex()]
        self._month_summary = dashboard_service.month_summary(y, m)
        self._render_month()

    def _render_day(self):
        s = self._summary
        tm = theme()

        # KPI values + subtitles
        self.rev_card.set_value(f"{s['revenue']:,.0f} EGP")
        self.rev_card.set_subtitle(t("dash.kpi.revenue_sub", count=s["revenue_count"]))
        self.exp_card.set_value(f"{s['expenses']:,.0f} EGP")
        self.exp_card.set_subtitle(t("dash.kpi.expenses_sub", count=s["expenses_count"]))
        net = s["net"]
        net_prefix = "+" if net > 0 else ""
        self.net_card.set_value(f"{net_prefix}{net:,.0f} EGP")
        self.net_card.set_subtitle(t("dash.kpi.net_sub"))
        self.att_card.set_value(str(s["attendance_total"]))
        self.att_card.set_subtitle(t("dash.kpi.attendance_sub"))

        # Comparison badges
        try:
            comps = dashboard_service.compare_day_to_baselines(self._selected_date)
        except Exception:
            comps = {}
        self._render_badges(comps)

        # Reconciliation strip
        try:
            recon = dashboard_service.daily_reconciliation(self._selected_date)
        except Exception:
            recon = {}
        self._render_reconciliation(recon)

        # Payments table
        self._render_payments()

        # 7-day table + chart
        self._render_week()

    def _render_badges(self, comps: dict):
        tm = theme()

        def _fmt(entry, prefix_key):
            """Return (arrow, text, color) or None if there's nothing to show."""
            if not entry:
                return None
            pct = entry.get("pct")
            if pct is None:
                # Baseline was zero — no meaningful percentage
                return (
                    "■",
                    f"{prefix_key}: —",
                    tm.color("text_secondary"),
                )
            abs_v = entry.get("absolute", 0)
            if abs_v > 0:
                arrow = "▲"
                color = tm.color("success")
            elif abs_v < 0:
                arrow = "▼"
                color = tm.color("danger")
            else:
                arrow = "■"
                color = tm.color("text_secondary")
            return (arrow, f"{prefix_key}: {pct:+.1f}%", color)

        for key, (lbl_y, lbl_wd, lbl_avg) in self._badge_labels.items():
            c = comps.get(key, {})
            rows = (
                (lbl_y,   c.get("yesterday"),    t("dash.badge.vs_yesterday")),
                (lbl_wd,  c.get("same_weekday"), t("dash.badge.vs_week")),
                (lbl_avg, c.get("week_avg"),     t("dash.badge.vs_avg")),
            )
            for lbl, entry, prefix_key in rows:
                result = _fmt(entry, prefix_key)
                if result is None:
                    lbl.setText("")
                    continue
                arrow, text, color = result
                lbl.setText(f"{arrow} {text}")
                lbl.setStyleSheet(
                    f"QLabel {{"
                    f"  color: {color};"
                    f"  background-color: transparent;"
                    f"  font-size: 11px;"
                    f"  font-weight: 600;"
                    f"}}"
                )

    def _render_reconciliation(self, recon: dict):
        tm = theme()
        cash = recon.get("cash_in", 0)
        transfer = recon.get("transfer_in", 0)
        self._recon_labels["payments"].setText(
            t("dash.reconcile.payments", count=recon.get("payments_count", 0))
        )
        self._recon_labels["payers"].setText(
            t("dash.reconcile.payers", count=recon.get("unique_payers", 0))
        )
        self._recon_labels["attendance"].setText(
            t("dash.reconcile.attendance", count=recon.get("attendance_count", 0))
        )
        self._recon_labels["cash"].setText(
            t("dash.reconcile.cash", amount=f"{cash:,.0f}")
        )
        self._recon_labels["transfer"].setText(
            t("dash.reconcile.transfer", amount=f"{transfer:,.0f}")
        )
        for key, lbl in self._recon_labels.items():
            lbl.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text')};"
                f"  background-color: transparent;"
                f"  font-size: 13px;"
                f"  padding: 4px 8px;"
                f"}}"
            )

    def _render_payments(self):
        try:
            rows = dashboard_service.payments_for_day_detailed(
                self._selected_date,
                sport_id=self._sport_filter_id,
                method=self._method_filter,
            )
        except Exception:
            rows = []

        if not rows:
            self.payments_card.hide()
            return
        self.payments_card.show()

        tm = theme()
        self.payments_table.setSortingEnabled(False)
        self.payments_table.setRowCount(len(rows))
        total = 0.0

        for i, p in enumerate(rows):
            # Time — extract from created_at if available, else dash
            when = p.get("created_at") or ""
            time_part = when.split(" ")[-1][:5] if " " in when else ""

            self.payments_table.setItem(i, 0, QTableWidgetItem(time_part))
            self.payments_table.setItem(i, 1, QTableWidgetItem(p["player_name"]))

            sport = (p.get("activity_name_ar") if i18n.current_language() == "ar"
                     else p.get("activity_name_en")) or "—"
            self.payments_table.setItem(i, 2, QTableWidgetItem(sport))

            amount_text = f"{p['amount']:,.0f} {p['currency']}"
            amount_item = QTableWidgetItem(amount_text)
            amount_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            amount_item.setForeground(QColor(tm.color("success")))
            self.payments_table.setItem(i, 3, amount_item)

            method = p.get("method") or "cash"
            self.payments_table.setItem(
                i, 4, QTableWidgetItem(t(f"dash.payments.method.{method}"))
            )

            self.payments_table.setItem(i, 5, QTableWidgetItem(p.get("notes") or ""))

            total += p["amount"]

        self.payments_table.setSortingEnabled(True)
        self.payments_total_label.setText(
            t("dash.payments.total", count=len(rows), amount=f"{total:,.0f}")
        )

    def _render_week(self):
        rows = []
        for i in range(6, -1, -1):
            d = self._selected_date - timedelta(days=i)
            try:
                s = dashboard_service.day_summary(d)
            except Exception:
                s = {"revenue": 0, "expenses": 0,
                     "attendance_total": 0, "new_players": 0}
            rows.append({
                "date": d,
                "weekday": WEEKDAY_KEYS[d.weekday()],
                "attendance": s.get("attendance_total", 0),
                "revenue": s.get("revenue", 0),
                "expenses": s.get("expenses", 0),
                "signups": s.get("new_players", 0),
            })

        self._week_rows = rows
        tm = theme()

        # ---- Combo chart ----
        chart_slots = []
        for r in rows:
            short = t(r["weekday"]).split()[0] if t(r["weekday"]) else ""
            chart_slots.append({
                "label": short,
                "key": r["date"].isoformat(),
                "values": [r["revenue"], r["expenses"]],
                "highlight": r["date"] == self._selected_date,
            })
        self.combo_chart.set_data(chart_slots)

        # ---- Table ----
        self.week_table.setRowCount(len(rows))
        tot_att = sum(r["attendance"] for r in rows)
        tot_rev = sum(r["revenue"] for r in rows)
        tot_sig = sum(r["signups"] for r in rows)

        for i, r in enumerate(rows):
            is_sel = (r["date"] == self._selected_date)

            self.week_table.setItem(i, 0, QTableWidgetItem(t(r["weekday"])))
            self.week_table.setItem(i, 1, QTableWidgetItem(r["date"].isoformat()))

            att_item = QTableWidgetItem(str(r["attendance"]))
            att_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.week_table.setItem(i, 2, att_item)

            rev_item = QTableWidgetItem(f"{r['revenue']:,.0f} EGP")
            rev_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.week_table.setItem(i, 3, rev_item)

            sig_item = QTableWidgetItem(str(r["signups"]))
            sig_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.week_table.setItem(i, 4, sig_item)

            if is_sel:
                bg = QColor(tm.color("primary_soft"))
                for c in range(5):
                    item = self.week_table.item(i, c)
                    if item:
                        item.setBackground(bg)

        # Total row
        total_row = self.week_table.rowCount()
        self.week_table.insertRow(total_row)

        lbl = QTableWidgetItem(t("dash.week.total"))
        lbl.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.week_table.setItem(total_row, 0, lbl)
        self.week_table.setItem(total_row, 1, QTableWidgetItem(""))

        att_t = QTableWidgetItem(str(tot_att))
        att_t.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_table.setItem(total_row, 2, att_t)

        rev_t = QTableWidgetItem(f"{tot_rev:,.0f} EGP")
        rev_t.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.week_table.setItem(total_row, 3, rev_t)

        sig_t = QTableWidgetItem(str(tot_sig))
        sig_t.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_table.setItem(total_row, 4, sig_t)

        total_bg = QColor(tm.color("surface_alt"))
        for c in range(5):
            item = self.week_table.item(total_row, c)
            if item:
                item.setBackground(total_bg)
                f = item.font()
                f.setBold(True)
                item.setFont(f)

    def _render_month(self):
        s = self._month_summary
        if s is None:
            return

        # ---- KPI cards ----
        self.m_rev_card.set_value(f"{s['revenue']:,.0f} EGP")
        self.m_rev_card.set_subtitle(
            t("dash.kpi.revenue_month_sub", count=s["revenue_count"])
        )
        self.m_exp_card.set_value(f"{s['expenses']:,.0f} EGP")
        self.m_exp_card.set_subtitle(
            t("dash.kpi.expenses_month_sub", count=s["expenses_count"])
        )
        net = s["net"]
        net_prefix = "+" if net > 0 else ""
        self.m_net_card.set_value(f"{net_prefix}{net:,.0f} EGP")
        self.m_net_card.set_subtitle(t("dash.kpi.net_month_sub"))
        self.m_att_card.set_value(str(s["attendance_total"]))
        self.m_att_card.set_subtitle(t("dash.kpi.attendance_month_sub"))

        # ---- Revenue by activity ----
        rev_rows = []
        for i, row in enumerate(s.get("revenue_by_activity", [])):
            rev_rows.append({
                "label": self._activity_display_name(row),
                "value": float(row["total"]),
                "count": int(row.get("count", 0)) or None,
                "suffix": " EGP",
                "color": BAR_COLOR_CYCLE[i % len(BAR_COLOR_CYCLE)],
            })
        self.m_by_act_bars.set_data(rev_rows)

        if not rev_rows:
            self.m_by_act_bars.hide()
            if hasattr(self, "m_by_act_empty"):
                self.m_by_act_empty.show()
        else:
            self.m_by_act_bars.show()
            if hasattr(self, "m_by_act_empty"):
                self.m_by_act_empty.hide()

        # ---- Expenses by category ----
        exp_rows = []
        for row in s.get("expenses_by_category", []):
            exp_rows.append({
                "label": t(f"expenses.cat.{row['category']}"),
                "value": float(row["total"]),
                "count": int(row.get("count", 0)) or None,
                "suffix": " EGP",
                "color": "danger",
            })
        self.m_by_cat_bars.set_data(exp_rows)

        # ---- Revenue by method ----
        method_rows = []
        for row in s.get("revenue_by_method", []):
            method_rows.append({
                "label": t(f"dash.payments.method.{row['method']}"),
                "value": float(row["total"]),
                "count": int(row.get("count", 0)) or None,
                "suffix": " EGP",
                "color": "success",
            })
        self.m_by_method_bars.set_data(method_rows)

    # ---------- helpers ----------

    def _activity_display_name(self, row: dict) -> str:
        if i18n.current_language() == "ar":
            return row.get("name_ar") or row.get("name_en") or ""
        return row.get("name_en") or row.get("name_ar") or ""

    # ---------- click handlers ----------

    def _on_week_row_clicked(self, row: int, _col: int):
        if row < 0 or row >= len(self._week_rows):
            return
        target = self._week_rows[row]["date"]
        if target == self._selected_date:
            return
        self._selected_date = target
        self._sync_date_input()
        self.refresh()

    def _on_chart_bar_clicked(self, key):
        try:
            target = date.fromisoformat(key)
        except (ValueError, TypeError):
            return
        if target == self._selected_date:
            return
        self._selected_date = target
        self._sync_date_input()
        self.refresh()