"""
Progress panel — v4 design.

Layout:
    ┌────────────────────────────────────────────────────────┐
    │  ┌─ KPI ─┐  ┌─ KPI ─┐  ┌─ KPI ─┐                       │
    │  │ Total │  │ Cycle │  │ Deny  │                       │
    │  └───────┘  └───────┘  └───────┘                       │
    │                                                        │
    │  ┌─ Monthly Attendance ────────────────────────────┐   │
    │  │  Month: [September 2025 ▾]                       │   │
    │  │  ┌────┬────┬────┬────┬────┬────┬────┐           │   │
    │  │  │ 1✓ │ 3✓ │ 5✕ │ 8— │ …  │    │    │           │   │
    │  │  └────┴────┴────┴────┴────┴────┴────┘           │   │
    │  └──────────────────────────────────────────────────┘   │
    │                                                        │
    │  ┌─ Subscription History ──────────────────────────┐   │
    │  │  Plan    Start        Expiry       Status       │   │
    │  │  ...                                             │   │
    │  └──────────────────────────────────────────────────┘   │
    └────────────────────────────────────────────────────────┘
"""

import os
import sys
import calendar
from datetime import date, datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_plan, get_plan_label
from services import subscription_service, attendance_service
from ui.components import SectionCard, KpiCard, Toolbar, EmptyState
from ui.theme import theme, ThemedWidget
from ui.design import SPACING, RADIUS
from ui.i18n import t


MONTH_KEYS = [
    "month.january", "month.february", "month.march", "month.april",
    "month.may", "month.june", "month.july", "month.august",
    "month.september", "month.october", "month.november", "month.december",
]

WEEKDAY_KEYS = {
    "Monday":    "weekday.monday",
    "Tuesday":   "weekday.tuesday",
    "Wednesday": "weekday.wednesday",
    "Thursday":  "weekday.thursday",
    "Friday":    "weekday.friday",
    "Saturday":  "weekday.saturday",
    "Sunday":    "weekday.sunday",
}


class ProgressPanel(ThemedWidget, QWidget):
    def __init__(self, player_id, parent=None):
        QWidget.__init__(self, parent)
        self.player_id = player_id
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, SPACING["lg"], 0, 0)
        root.setSpacing(SPACING["lg"])

        # ---------- KPI row ----------
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(SPACING["md"])

        self.total_card = KpiCard(t("progress.total"), "0")
        self.cycle_card = KpiCard(t("progress.cycle"), "0")
        self.denial_card = KpiCard(t("progress.denials"), "0")

        for c in (self.total_card, self.cycle_card, self.denial_card):
            kpi_row.addWidget(c, stretch=1)

        root.addLayout(kpi_row)

        # ---------- Monthly attendance card ----------
        self.month_card = SectionCard(title=t("progress.monthly_group"))

        # Month selector inside a Toolbar (RTL-aware)
        self.month_toolbar = Toolbar()
        self.month_selector = QComboBox()

        today = date.today()
        self._month_options = []
        for i in range(5, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            self._month_options.append((y, m))
            self.month_selector.addItem(f"{t(MONTH_KEYS[m-1])} {y}")
        self.month_selector.setCurrentIndex(len(self._month_options) - 1)
        self.month_selector.currentIndexChanged.connect(self._render_month_grid)

        self.month_label = QLabel(t("progress.month_label"))
        self.month_toolbar.add_leading(self.month_label)
        self.month_toolbar.add_leading(self.month_selector)

        self.month_card.body.addWidget(self.month_toolbar)

        # Grid container for the day cells
        self.month_grid_container = QWidget()
        self.month_grid_layout = QGridLayout(self.month_grid_container)
        self.month_grid_layout.setHorizontalSpacing(SPACING["xs"])
        self.month_grid_layout.setVerticalSpacing(SPACING["xs"])
        self.month_grid_layout.setContentsMargins(0, SPACING["sm"], 0, 0)
        self.month_card.body.addWidget(self.month_grid_container)

        # Empty-state widget shown when there is no active subscription
        self.month_empty = EmptyState(
            icon="📅",
            message=t("progress.month.no_sub_note"),
        )
        self.month_empty.hide()
        self.month_card.body.addWidget(self.month_empty)

        root.addWidget(self.month_card)

        # ---------- Subscription history card ----------
        self.history_card = SectionCard(title=t("progress.history_group"))

        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels([
            t("progress.history.plan"),
            t("progress.history.start"),
            t("progress.history.expiry"),
            t("progress.history.status"),
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setShowGrid(False)
        self.history_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_card.body.addWidget(self.history_table)

        root.addWidget(self.history_card)

        # Add a stretcher so the panel doesn't get squeezed
        root.addStretch()

    # ---------- theme ----------

    def restyle(self):
        tm = theme()

        # Explicit colorization of the KPI values, since KpiCard's
        # default value color is neutral. We want:
        #   total   → primary   (informational)
        #   cycle   → success   (progress)
        #   denials → danger    (attention)
        self._style_kpi_value(self.total_card, tm.color("primary"))
        self._style_kpi_value(self.cycle_card, tm.color("success"))
        self._style_kpi_value(self.denial_card, tm.color("danger"))

        if hasattr(self, "_month_options"):
            self._render_month_grid()
        self._render_history()

    @staticmethod
    def _style_kpi_value(kpi: KpiCard, color: str):
        kpi.value_label.setStyleSheet(
            f"QLabel#kpiValue {{"
            f"  color: {color};"
            f"  background-color: transparent;"
            f"  font-size: 22px;"
            f"  font-weight: 700;"
            f"}}"
        )

    # ---------- data ----------

    def refresh(self):
        attendance = attendance_service.get_for_player(self.player_id)
        active_sub = subscription_service.get_active(self.player_id)

        total_attended = sum(1 for e in attendance if e.result == "allowed")
        denial_count = sum(1 for e in attendance if e.result == "denied")
        cycle_attended = 0
        if active_sub:
            cycle_attended = sum(
                1 for e in attendance
                if e.result == "allowed" and e.subscription_id == active_sub.subscription_id
            )

        self.total_card.set_value(total_attended)
        self.cycle_card.set_value(cycle_attended)
        self.denial_card.set_value(denial_count)

        self._attendance_cache = attendance
        self._active_sub_cache = active_sub
        self._render_month_grid()
        self._render_history()

    def _render_history(self):
        history = subscription_service.get_history(self.player_id)
        self.history_table.setRowCount(len(history))
        tm = theme()
        for i, sub in enumerate(history):
            self.history_table.setItem(i, 0, QTableWidgetItem(get_plan_label(sub.plan_type)))
            self.history_table.setItem(i, 1, QTableWidgetItem(sub.start_date))
            self.history_table.setItem(i, 2, QTableWidgetItem(sub.expiry_date))

            status_key = {
                "active":    "progress.sub.status.active",
                "expired":   "progress.sub.status.expired",
                "suspended": "progress.sub.status.suspended",
            }.get(sub.status, "players.status.none")

            status_item = QTableWidgetItem(t(status_key))
            color_token = {
                "active": "success", "expired": "danger", "suspended": "warning",
            }.get(sub.status, "text_secondary")
            status_item.setForeground(QColor(tm.color(color_token)))
            self.history_table.setItem(i, 3, status_item)

    def _render_month_grid(self):
        # Clear existing cells
        while self.month_grid_layout.count():
            item = self.month_grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not hasattr(self, "_month_options"):
            return

        tm = theme()
        year, month = self._month_options[self.month_selector.currentIndex()]

        active_sub = getattr(self, "_active_sub_cache", None)
        attendance = getattr(self, "_attendance_cache", [])

        # Toggle between the grid and the empty state
        if not active_sub:
            self.month_grid_container.hide()
            self.month_empty.show()
            return
        else:
            self.month_grid_container.show()
            self.month_empty.hide()

        attended_dates = {
            datetime.fromisoformat(e.scan_datetime).date()
            for e in attendance if e.result == "allowed"
        }

        plan = get_plan(active_sub.plan_type)
        allowed_weekday_names = set(plan["allowed_days"])

        today = date.today()
        days_in_month = calendar.monthrange(year, month)[1]

        # 7 columns max, flow left-to-right (Qt mirrors in RTL)
        col = 0
        row = 0
        max_cols = 7
        for day_num in range(1, days_in_month + 1):
            d = date(year, month, day_num)
            weekday_name = d.strftime("%A")
            if weekday_name not in allowed_weekday_names:
                continue

            if d in attended_dates:
                text = f"{day_num}  ✓"
                color = tm.color("success")
                bg = tm.color("success_soft")
            elif d < today:
                text = f"{day_num}  ✕"
                color = tm.color("danger")
                bg = tm.color("danger_soft")
            else:
                text = f"{day_num}  —"
                color = tm.color("text_secondary")
                bg = tm.color("surface_alt")

            cell = QLabel(text)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setStyleSheet(
                f"QLabel {{"
                f"  border: 1px solid {tm.color('border')};"
                f"  border-radius: {RADIUS['sm']}px;"
                f"  padding: 10px 8px;"
                f"  color: {color};"
                f"  font-weight: 600;"
                f"  font-size: 13px;"
                f"  background-color: {bg};"
                f"}}"
            )
            self.month_grid_layout.addWidget(cell, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1