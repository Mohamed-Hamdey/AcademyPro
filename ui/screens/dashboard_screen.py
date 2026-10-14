"""
Manager dashboard — daily view.

Shows revenue, expenses, net, attendance for a chosen day, plus payment
list, new signups, and alerts (low sessions, expiring soon).

Manager-only. Wrapped in a scroll area so nothing clips when the window
is short.
"""

import os
import sys
from datetime import date, timedelta

from PyQt6.QtWidgets import (
    QComboBox, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor



sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import dashboard_service, activity_service
from ui.components import SectionCard, KpiCard, Toolbar, EmptyState
from ui.theme import theme, ThemedWidget, make_secondary, make_danger
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui import i18n



MONTH_KEYS = [
    "month.january", "month.february", "month.march", "month.april",
    "month.may", "month.june", "month.july", "month.august",
    "month.september", "month.october", "month.november", "month.december",
]
class DashboardScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._selected_date = date.today()
        self._summary = None
        self._build_ui()
        self.refresh()
        self._init_theme()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        from PyQt6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()

        # ============ DAILY TAB ============
        daily = QWidget()
        daily_root = QVBoxLayout(daily)
        daily_root.setContentsMargins(0, SPACING["lg"], 0, 0)
        daily_root.setSpacing(SPACING["lg"])
        self.tabs.addTab(daily, t("dash.tab.daily"))

        self._build_daily_page(daily_root)

        # ============ MONTHLY TAB ============
        monthly = QWidget()
        monthly_root = QVBoxLayout(monthly)
        monthly_root.setContentsMargins(0, SPACING["lg"], 0, 0)
        monthly_root.setSpacing(SPACING["lg"])
        self.tabs.addTab(monthly, t("dash.tab.monthly"))

        self._build_monthly_page(monthly_root)

        root.addWidget(self.tabs, stretch=1)

    def _build_daily_page(self, root):
        # ---------- Date navigation toolbar ----------
        self.toolbar = Toolbar()
        self.prev_button = QPushButton("◀  " + t("dash.prev_day"))
        make_secondary(self.prev_button)
        self.prev_button.clicked.connect(self._on_prev_day)

        self.today_button = QPushButton(t("dash.jump_today"))
        make_secondary(self.today_button)
        self.today_button.clicked.connect(self._on_jump_today)

        self.next_button = QPushButton(t("dash.next_day") + "  ▶")
        make_secondary(self.next_button)
        self.next_button.clicked.connect(self._on_next_day)

        self.date_label = QLabel()
        self.date_label.setStyleSheet("font-size: 14px; font-weight: 700;")

        self.toolbar.add_leading(self.prev_button)
        self.toolbar.add_leading(self.today_button)
        self.toolbar.add_leading(self.next_button)
        self.toolbar.add_leading(self.date_label)

        root.addWidget(self.toolbar)

        # ---------- Scrollable content ----------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(SPACING["lg"])

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(SPACING["md"])

        self.rev_card       = KpiCard(t("dash.kpi.revenue"), "0")
        self.exp_card       = KpiCard(t("dash.kpi.expenses"), "0")
        self.net_card       = KpiCard(t("dash.kpi.net"), "0")
        self.att_card       = KpiCard(t("dash.kpi.attendance"), "0")

        for c in (self.rev_card, self.exp_card, self.net_card, self.att_card):
            kpi_row.addWidget(c, stretch=1)
        body.addLayout(kpi_row)

        # Row 2: attendance by activity + payments
        row2 = QHBoxLayout()
        row2.setSpacing(SPACING["lg"])

        self.attendance_card = SectionCard(title=t("dash.by_activity"))
        self.attendance_list = QListWidget()
        self.attendance_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.attendance_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.attendance_list.setMinimumHeight(180)
        self.attendance_card.body.addWidget(self.attendance_list)
        self.attendance_empty = EmptyState(
            icon="🎟", message=t("dash.by_activity_empty"),
        )
        self.attendance_empty.hide()
        self.attendance_card.body.addWidget(self.attendance_empty)
        row2.addWidget(self.attendance_card, stretch=1)

        self.payments_card = SectionCard(title=t("dash.payments"))
        self.payments_list = QListWidget()
        self.payments_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.payments_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.payments_list.setMinimumHeight(180)
        self.payments_card.body.addWidget(self.payments_list)
        self.payments_empty = EmptyState(
            icon="💵", message=t("dash.payments_empty"),
        )
        self.payments_empty.hide()
        self.payments_card.body.addWidget(self.payments_empty)
        row2.addWidget(self.payments_card, stretch=1)

        body.addLayout(row2)

        # Row 3: new signups + alerts
        row3 = QHBoxLayout()
        row3.setSpacing(SPACING["lg"])

        self.signups_card = SectionCard(title=t("dash.signups"))
        self.signups_list = QListWidget()
        self.signups_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.signups_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.signups_list.setMinimumHeight(180)
        self.signups_card.body.addWidget(self.signups_list)
        self.signups_empty = EmptyState(
            icon="👤", message=t("dash.signups_empty"),
        )
        self.signups_empty.hide()
        self.signups_card.body.addWidget(self.signups_empty)
        row3.addWidget(self.signups_card, stretch=1)

        self.alerts_card = SectionCard(title=t("dash.alerts"))
        self.alerts_list = QListWidget()
        self.alerts_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.alerts_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.alerts_list.setMinimumHeight(180)
        self.alerts_card.body.addWidget(self.alerts_list)
        self.alerts_empty = EmptyState(
            icon="✅", message=t("dash.alerts_empty"),
        )
        self.alerts_empty.hide()
        self.alerts_card.body.addWidget(self.alerts_empty)
        row3.addWidget(self.alerts_card, stretch=1)

        body.addLayout(row3)

        # Footer buttons
        footer = QHBoxLayout()
        footer.setSpacing(SPACING["sm"])

        self.print_button = QPushButton(t("dash.print_day"))
        make_secondary(self.print_button)
        self.print_button.clicked.connect(self._on_print)
        self.print_button.setEnabled(False)   # enabled in 4.4

        self.close_button = QPushButton(t("dash.close_day"))
        make_danger(self.close_button)
        self.close_button.clicked.connect(self._on_close_day)
        self.close_button.setEnabled(False)   # enabled in 4.4

        footer.addStretch()
        footer.addWidget(self.print_button)
        footer.addWidget(self.close_button)
        body.addLayout(footer)

        body.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    # ---------- theming ----------
    def _build_monthly_page(self, root):
        """Monthly dashboard content."""
        # Month navigation
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

        # Month scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(SPACING["lg"])

        # KPIs
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(SPACING["md"])
        self.m_rev_card = KpiCard(t("dash.kpi.revenue"), "0")
        self.m_exp_card = KpiCard(t("dash.kpi.expenses"), "0")
        self.m_net_card = KpiCard(t("dash.kpi.net"), "0")
        self.m_att_card = KpiCard(t("dash.kpi.attendance"), "0")
        for c in (self.m_rev_card, self.m_exp_card, self.m_net_card, self.m_att_card):
            kpi_row.addWidget(c, stretch=1)
        body.addLayout(kpi_row)

        # Row 2: Revenue by activity + expenses by category
        row2 = QHBoxLayout()
        row2.setSpacing(SPACING["lg"])

        self.m_by_act_card = SectionCard(title=t("dash.month.by_activity"))
        self.m_by_act_list = QListWidget()
        self.m_by_act_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.m_by_act_list.setMinimumHeight(180)
        self.m_by_act_card.body.addWidget(self.m_by_act_list)
        row2.addWidget(self.m_by_act_card, stretch=1)

        self.m_by_cat_card = SectionCard(title=t("dash.month.expenses_by_category"))
        self.m_by_cat_list = QListWidget()
        self.m_by_cat_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.m_by_cat_list.setMinimumHeight(180)
        self.m_by_cat_card.body.addWidget(self.m_by_cat_list)
        row2.addWidget(self.m_by_cat_card, stretch=1)

        body.addLayout(row2)

        # Row 3: revenue by method
        self.m_by_method_card = SectionCard(title=t("dash.month.by_method"))
        self.m_by_method_list = QListWidget()
        self.m_by_method_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.m_by_method_list.setMinimumHeight(120)
        self.m_by_method_card.body.addWidget(self.m_by_method_list)
        body.addWidget(self.m_by_method_card)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(SPACING["sm"])
        self.m_print_button = QPushButton(t("dash.print_month"))
        make_secondary(self.m_print_button)
        self.m_print_button.setEnabled(False)   # Batch 4.4
        self.m_close_button = QPushButton(t("dash.close_month"))
        make_danger(self.m_close_button)
        self.m_close_button.setEnabled(False)   # Batch 4.4
        footer.addStretch()
        footer.addWidget(self.m_print_button)
        footer.addWidget(self.m_close_button)
        body.addLayout(footer)

        body.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    def _on_month_changed(self, _idx):
        self._render_month()

    def _render_month(self):
        from services import dashboard_service
        from ui import i18n
        y, m = self._month_options[self.month_selector.currentIndex()]
        s = dashboard_service.month_summary(y, m)

        self.m_rev_card.set_value(f"{s['revenue']:,.0f} EGP")
        self.m_rev_card.set_subtitle(
            t("dash.kpi.revenue_sub", count=s["revenue_count"])
        )
        self.m_exp_card.set_value(f"{s['expenses']:,.0f} EGP")
        self.m_exp_card.set_subtitle(
            t("dash.kpi.expenses_sub", count=s["expenses_count"])
        )
        net = s["net"]
        net_prefix = "+" if net > 0 else ""
        self.m_net_card.set_value(f"{net_prefix}{net:,.0f} EGP")
        self.m_net_card.set_subtitle(t("dash.kpi.net_sub"))
        self.m_att_card.set_value(str(s["attendance_total"]))
        self.m_att_card.set_subtitle(t("dash.kpi.attendance_sub"))

        # Revenue by activity
        self.m_by_act_list.clear()
        if not s["revenue_by_activity"]:
            item = QListWidgetItem(t("dash.month.no_data"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.m_by_act_list.addItem(item)
        else:
            tm = theme()
            for row in s["revenue_by_activity"]:
                name = (row.get("name_ar") or row.get("name_en") or "?"
                        if i18n.current_language() == "ar"
                        else row.get("name_en") or row.get("name_ar") or "?")
                text = f"{name}:   {row['total']:,.0f} EGP   ({row['count']})"
                item = QListWidgetItem(text)
                item.setForeground(QColor(tm.color("text")))
                self.m_by_act_list.addItem(item)

        # Expenses by category
        self.m_by_cat_list.clear()
        if not s["expenses_by_category"]:
            item = QListWidgetItem(t("dash.month.no_data"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.m_by_cat_list.addItem(item)
        else:
            tm = theme()
            for row in s["expenses_by_category"]:
                name = t(f"expenses.cat.{row['category']}")
                text = f"{name}:   {row['total']:,.0f} EGP   ({row['count']})"
                item = QListWidgetItem(text)
                item.setForeground(QColor(tm.color("danger")))
                self.m_by_cat_list.addItem(item)

        # Revenue by method
        self.m_by_method_list.clear()
        if not s["revenue_by_method"]:
            item = QListWidgetItem(t("dash.month.no_data"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.m_by_method_list.addItem(item)
        else:
            tm = theme()
            for row in s["revenue_by_method"]:
                text = f"{row['method']}:   {row['total']:,.0f} EGP   ({row['count']})"
                item = QListWidgetItem(text)
                item.setForeground(QColor(tm.color("text")))
                self.m_by_method_list.addItem(item)
    def restyle(self):
        tm = theme()

        self.date_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 14px;"
            f"  font-weight: 700;"
            f"  padding: 0 8px;"
            f"}}"
        )

        self._style_kpi(self.rev_card, tm.color("success"))
        self._style_kpi(self.exp_card, tm.color("danger"))
        self._style_kpi(self.net_card, tm.color("primary"))
        self._style_kpi(self.att_card, tm.color("text"))

        for lst in (self.attendance_list, self.payments_list,
                    self.signups_list, self.alerts_list):
            lst.setStyleSheet(
                f"QListWidget {{"
                f"  background-color: transparent;"
                f"  border: none;"
                f"  padding: 0;"
                f"  outline: none;"
                f"}}"
                f"QListWidget::item {{"
                f"  padding: 8px 10px;"
                f"  border-radius: {RADIUS['xs']}px;"
                f"  color: {tm.color('text')};"
                f"}}"
                f"QListWidget::item:hover {{"
                f"  background-color: {tm.color('surface_alt')};"
                f"}}"
            )

        if self._summary is not None:
            self._render()

    @staticmethod
    def _style_kpi(kpi: KpiCard, color: str):
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
        self.refresh()

    def _on_next_day(self):
        self._selected_date += timedelta(days=1)
        self.refresh()

    def _on_jump_today(self):
        self._selected_date = date.today()
        self.refresh()

    # ---------- data ----------

    def refresh(self):
        self._summary = dashboard_service.day_summary(self._selected_date)
        self._render()
        # Also refresh the month tab
        if hasattr(self, "_month_options"):
            self._render_month()

    def _render(self):
        s = self._summary

        # Date label
        is_today = self._selected_date == date.today()
        label = self._selected_date.isoformat()
        if is_today:
            label += "  (" + t("dash.today") + ")"
        self.date_label.setText(label)

        # KPIs
        self.rev_card.set_value(f"{s['revenue']:,.0f} EGP")
        self.rev_card.set_subtitle(
            t("dash.kpi.revenue_sub", count=s["revenue_count"])
        )

        self.exp_card.set_value(f"{s['expenses']:,.0f} EGP")
        self.exp_card.set_subtitle(
            t("dash.kpi.expenses_sub", count=s["expenses_count"])
        )

        net = s["net"]
        net_prefix = "+" if net > 0 else ""
        self.net_card.set_value(f"{net_prefix}{net:,.0f} EGP")
        self.net_card.set_subtitle(t("dash.kpi.net_sub"))

        self.att_card.set_value(str(s["attendance_total"]))
        self.att_card.set_subtitle(t("dash.kpi.attendance_sub"))

        # Attendance by activity
        self.attendance_list.clear()
        by_act = s["attendance_by_activity"]
        if not by_act:
            self.attendance_list.hide()
            self.attendance_empty.show()
        else:
            self.attendance_list.show()
            self.attendance_empty.hide()
            tm = theme()
            for row in by_act:
                act_name = self._activity_display_name(row)
                text = f"{act_name}:   {row['cnt']}"
                item = QListWidgetItem(text)
                item.setForeground(QColor(tm.color("text")))
                self.attendance_list.addItem(item)
            # Total row
            total_item = QListWidgetItem(
                f"────\n{t('dash.total')}:   {s['attendance_total']}"
            )
            total_item.setForeground(QColor(tm.color("text_secondary")))
            self.attendance_list.addItem(total_item)

        # Payments
        self.payments_list.clear()
        payments = s["payments"]
        if not payments:
            self.payments_list.hide()
            self.payments_empty.show()
        else:
            self.payments_list.show()
            self.payments_empty.hide()
            tm = theme()
            for p in payments:
                amount = f"{p['amount']:,.0f} {p['currency']}"
                act = self._activity_display_name({
                    "name_en": p.get("activity_name_en"),
                    "name_ar": p.get("activity_name_ar"),
                })
                note = p.get("notes") or ""
                text = f"{p['player_name']}   —   {amount}"
                if act:
                    text += f"   ·   {act}"
                if note:
                    text += f"\n     {note}"
                item = QListWidgetItem(text)
                item.setForeground(QColor(tm.color("text")))
                self.payments_list.addItem(item)

        # Signups
        self.signups_list.clear()
        new_players = s["new_player_list"]
        if not new_players:
            self.signups_list.hide()
            self.signups_empty.show()
        else:
            self.signups_list.show()
            self.signups_empty.hide()
            tm = theme()
            for p in new_players:
                text = f"{p['full_name']}   ·   {p['phone']}"
                item = QListWidgetItem(text)
                item.setForeground(QColor(tm.color("text")))
                self.signups_list.addItem(item)

        # Alerts
        self.alerts_list.clear()
        alerts = []
        for lp in s["low_session_players"]:
            act = self._activity_display_name({
                "name_en": lp.get("activity_name_en"),
                "name_ar": lp.get("activity_name_ar"),
            })
            alerts.append(
                t("dash.alert.low_sessions",
                  name=lp["full_name"],
                  count=lp["sessions_remaining"],
                  activity=act or "")
            )
        for exp in s["expiring_soon"]:
            act = self._activity_display_name({
                "name_en": exp.get("activity_name_en"),
                "name_ar": exp.get("activity_name_ar"),
            })
            alerts.append(
                t("dash.alert.expiring_soon",
                  name=exp["full_name"],
                  date=exp["expiry_date"],
                  activity=act or "")
            )

        if not alerts:
            self.alerts_list.hide()
            self.alerts_empty.show()
        else:
            self.alerts_list.show()
            self.alerts_empty.hide()
            tm = theme()
            for a in alerts:
                item = QListWidgetItem(a)
                item.setForeground(QColor(tm.color("warning")))
                self.alerts_list.addItem(item)

    # ---------- helpers ----------

    def _activity_display_name(self, row: dict) -> str:
        """Prefer Arabic if the app is in Arabic, else English."""
        if i18n.current_language() == "ar":
            return row.get("name_ar") or row.get("name_en") or ""
        return row.get("name_en") or row.get("name_ar") or ""

    # ---------- actions (stubs) ----------

    def _on_print(self):
        # Enabled in Batch 4.4
        pass

    def _on_close_day(self):
        # Enabled in Batch 4.4
        pass