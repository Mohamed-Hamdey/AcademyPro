"""
Player Records & Activity tab — merged Progress + History.

One scrolling page with:
  1. KPI cards (4 metrics with context subtitles)
  2. Monthly attendance grid
  3. Subscription history cards
  4. Event timeline grouped by month

A single Print button in the top toolbar exports everything to a
detailed PDF / prints it.

Replaces the old separate ProgressPanel and PlayerHistoryTab.
"""

import os
import sys
import calendar
from datetime import date, datetime, timedelta
from collections import OrderedDict

from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QComboBox,
    QFrame, QPushButton, QListWidget, QListWidgetItem,
)
from qtpy.QtCore import Qt,QTimer
from qtpy.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_plan_label
from services import (
    subscription_service, attendance_service, activity_service, history_service,
)
from ui.components import SectionCard, KpiCard, Toolbar, EmptyState
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.message_box import info


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


class PlayerRecordsTab(ThemedWidget, QWidget):
    def __init__(self, player_id: int, player_name: str = "", parent=None):
        QWidget.__init__(self, parent)
        self.player_id = player_id
        self.player_name = player_name

        # Caches filled by refresh()
        self._attendance = []
        self._active_subs = []
        self._all_subs = []
        self._events = []

        self._build_ui()
        QTimer.singleShot(0, self.refresh)
        self._init_theme()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, SPACING["lg"], 0, 0)
        root.setSpacing(SPACING["lg"])

        # ---------- Toolbar with Print ----------
        self.toolbar = Toolbar()

        self.print_button = QPushButton(t("history.print"))
        make_secondary(self.print_button)
        self.print_button.clicked.connect(self._on_print)

        self.toolbar.add_trailing(self.print_button)
        root.addWidget(self.toolbar)

        # ---------- KPI cards ----------
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(SPACING["md"])

        self.total_card     = KpiCard(t("progress.kpi.total"),      "0")
        self.month_card     = KpiCard(t("progress.kpi.this_month"), "0")
        self.rate_card      = KpiCard(t("progress.kpi.rate"),       "—")
        self.remaining_card = KpiCard(t("progress.kpi.remaining"),  "—")

        for c in (self.total_card, self.month_card, self.rate_card, self.remaining_card):
            kpi_row.addWidget(c, stretch=1)
        root.addLayout(kpi_row)

        # ---------- Monthly attendance card ----------
        self.attendance_card = SectionCard(title=t("progress.monthly_group"))

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
        self.attendance_card.body.addWidget(self.month_toolbar)

        self.days_label = QLabel()
        self.days_label.setWordWrap(True)
        self.attendance_card.body.addWidget(self.days_label)

        self.month_grid_container = QWidget()
        self.month_grid_layout = QGridLayout(self.month_grid_container)
        self.month_grid_layout.setHorizontalSpacing(SPACING["xs"])
        self.month_grid_layout.setVerticalSpacing(SPACING["xs"])
        self.month_grid_layout.setContentsMargins(0, SPACING["sm"], 0, 0)
        self.attendance_card.body.addWidget(self.month_grid_container)

        self.month_empty = EmptyState(
            icon="📅",
            message=t("progress.month.no_sub_note"),
        )
        self.month_empty.hide()
        self.attendance_card.body.addWidget(self.month_empty)

        root.addWidget(self.attendance_card)

        # ---------- Subscription history ----------
        self.subs_card = SectionCard(title=t("progress.history_group"))

        self.subs_container = QWidget()
        self.subs_layout = QVBoxLayout(self.subs_container)
        self.subs_layout.setContentsMargins(0, 0, 0, 0)
        self.subs_layout.setSpacing(SPACING["sm"])
        self.subs_card.body.addWidget(self.subs_container)

        self.subs_empty = EmptyState(
            icon="📋",
            message=t("progress.history.empty"),
        )
        self.subs_empty.hide()
        self.subs_card.body.addWidget(self.subs_empty)

        root.addWidget(self.subs_card)

        # ---------- Event timeline ----------
        self.timeline_card = SectionCard(title=t("history.title"))

        self.timeline = QListWidget()
        self.timeline.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.timeline.setFrameShape(QListWidget.Shape.NoFrame)
        self.timeline.setWordWrap(True)
        self.timeline.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.timeline.customContextMenuRequested.connect(self._on_timeline_context_menu)
        self.timeline_card.body.addWidget(self.timeline)

        self.timeline_empty = EmptyState(
            icon="🗂",
            message=t("history.empty"),
        )
        self.timeline_empty.hide()
        self.timeline_card.body.addWidget(self.timeline_empty)

        root.addWidget(self.timeline_card)
        root.addStretch()

    # ---------- theming ----------

    def restyle(self):
        tm = theme()

        self._style_kpi(self.total_card,     tm.color("primary"))
        self._style_kpi(self.month_card,     tm.color("success"))
        self._style_kpi(self.rate_card,      tm.color("warning"))
        self._style_kpi(self.remaining_card, tm.color("text"))

        self.days_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"  padding: 4px 0;"
            f"}}"
        )
        self.timeline.setStyleSheet(
            f"QListWidget {{"
            f"  background-color: transparent;"
            f"  border: none;"
            f"  padding: 0;"
            f"  outline: none;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 6px 10px;"
            f"  color: {tm.color('text')};"
            f"}}"
        )

        if hasattr(self, "_month_options"):
            self._render_month_grid()
        self._render_subs()
        self._render_timeline()

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

    # ---------- data ----------

    def refresh(self):
        self._attendance = attendance_service.get_for_player(self.player_id)
        self._active_subs = subscription_service.get_all_active(self.player_id)
        self._all_subs = subscription_service.get_history(self.player_id)
        self._events = history_service.get_timeline(self.player_id)

        # Total paid (from the ledger)
        try:
            from services import payment_service
            self._payments = payment_service.list_for_player(self.player_id)
        except Exception:
            self._payments = []

        self._render_kpis()
        self._render_month_grid()
        self._render_subs()
        self._render_timeline()

    # ---------- KPIs ----------

    def _render_kpis(self):
        allowed = [e for e in self._attendance if e.result == "allowed"]
        total_attended = len(allowed)

        today = date.today()
        month_prefix = f"{today.year:04d}-{today.month:02d}"
        this_month = sum(1 for e in allowed if e.scan_datetime.startswith(month_prefix))
        training_days_in_month = self._count_training_days_this_month(today)

        cutoff = today - timedelta(days=30)
        expected = self._count_training_days_between(cutoff, today)
        attended_recent = sum(
            1 for e in allowed if _parse_date(e.scan_datetime) >= cutoff
        )
        rate = f"{int(round(100 * attended_recent / expected))}%" if expected > 0 else "—"

        if self._active_subs:
            remaining = sum(s.sessions_remaining for s in self._active_subs)
            total = sum(s.sessions_total for s in self._active_subs)
            remaining_text = f"{remaining} / {total}"
        else:
            remaining_text = "—"

        self.total_card.set_value(total_attended)
        self.total_card.set_subtitle(
            t("progress.kpi.total_sub", start=self._earliest_sub_start())
        )
        self.month_card.set_value(this_month)
        self.month_card.set_subtitle(
            t("progress.kpi.this_month_sub", count=training_days_in_month)
        )
        self.rate_card.set_value(rate)
        self.rate_card.set_subtitle(t("progress.kpi.rate_sub"))
        self.remaining_card.set_value(remaining_text)
        if self._active_subs:
            self.remaining_card.set_subtitle(t("progress.kpi.remaining_sub"))
        else:
            self.remaining_card.set_subtitle(t("progress.kpi.remaining_none"))

        # Total paid from ledger
        total_paid = sum(p.amount for p in getattr(self, "_payments", []))
        if total_paid > 0:
            self.total_card.set_subtitle(
                t("progress.kpi.total_sub_with_paid",
                  start=self._earliest_sub_start(),
                  paid=f"{total_paid:,.0f}")
            )

    def _earliest_sub_start(self) -> str:
        if self._all_subs:
            return min(s.start_date for s in self._all_subs)
        return date.today().isoformat()

    def _count_training_days_this_month(self, today: date) -> int:
        if not self._active_subs:
            return 0
        first = date(today.year, today.month, 1)
        last = date(today.year, today.month,
                    calendar.monthrange(today.year, today.month)[1])
        return self._count_training_days_between(first, last)

    def _count_training_days_between(self, start: date, end: date) -> int:
        if not self._active_subs:
            return 0
        weekdays = set()
        for s in self._active_subs:
            for d in (s.allowed_days or []):
                weekdays.add(d)
        count = 0
        d = start
        while d <= end:
            if d.strftime("%A") in weekdays:
                count += 1
            d += timedelta(days=1)
        return count

    # ---------- month grid ----------

    def _render_month_grid(self):
        while self.month_grid_layout.count():
            item = self.month_grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not hasattr(self, "_month_options"):
            return

        tm = theme()
        year, month = self._month_options[self.month_selector.currentIndex()]

        if not self._active_subs:
            self.month_grid_container.hide()
            self.days_label.hide()
            self.month_empty.show()
            return

        self.month_grid_container.show()
        self.days_label.show()
        self.month_empty.hide()

        weekdays = set()
        for s in self._active_subs:
            for d in (s.allowed_days or []):
                weekdays.add(d)
        self.days_label.setText(
            t("progress.training_days",
              days=", ".join(t(f"weekday.{d.lower()}") for d in sorted(weekdays)))
        )

        attended_dates = {
            _parse_date(e.scan_datetime)
            for e in self._attendance if e.result == "allowed"
        }
        earliest_start = min(_parse_date(s.start_date) for s in self._active_subs)
        latest_expiry = max(_parse_date(s.expiry_date) for s in self._active_subs)

        today = date.today()
        days_in_month = calendar.monthrange(year, month)[1]

        col = 0
        row = 0
        max_cols = 7
        for day_num in range(1, days_in_month + 1):
            d = date(year, month, day_num)
            if d.strftime("%A") not in weekdays:
                continue

            if d in attended_dates:
                text, color = f"{day_num}  ✓", tm.color("success")
                bg = tm.color("success_soft")
            elif d < earliest_start or d > latest_expiry:
                text, color = f"{day_num}  ·", tm.color("text_disabled")
                bg = tm.color("surface_alt")
            elif d > today:
                text, color = f"{day_num}  ◌", tm.color("text_secondary")
                bg = tm.color("surface_alt")
            else:
                text, color = f"{day_num}  ✕", tm.color("danger")
                bg = tm.color("danger_soft")

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

    # ---------- subscription cards ----------

    def _render_subs(self):
        while self.subs_layout.count():
            item = self.subs_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self._all_subs:
            self.subs_container.hide()
            self.subs_empty.show()
            return

        self.subs_container.show()
        self.subs_empty.hide()

        tm = theme()
        for sub in self._all_subs:
            self.subs_layout.addWidget(self._make_sub_card(sub, tm))

    def _make_sub_card(self, sub, tm) -> QFrame:
        card = QFrame()
        card.setObjectName("subCard")
        card.setStyleSheet(
            f"QFrame#subCard {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['md']}px;"
            f"}}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACING["md"], SPACING["sm"],
                                  SPACING["md"], SPACING["sm"])
        layout.setSpacing(4)

        title_row = QHBoxLayout()
        act = activity_service.get(sub.activity_id) if sub.activity_id else None
        act_name = activity_service.get_localized_name(act) if act else "—"
        plan_text = get_plan_label(sub.plan_type) if sub.plan_type else t("detail.sub.custom")

        title_label = QLabel(f"{plan_text} · {act_name}")
        title_label.setStyleSheet(
            f"QLabel {{ color: {tm.color('text')}; font-size: 14px; font-weight: 700; }}"
        )
        title_row.addWidget(title_label)
        title_row.addStretch()

        status_text = {
            "active":    t("players.status.active"),
            "expired":   t("players.status.expired"),
            "suspended": t("players.status.suspended"),
        }.get(sub.status, t("players.status.none"))
        color_token = {"active": "success", "expired": "danger",
                       "suspended": "warning"}.get(sub.status, "text_secondary")
        soft_token = {"active": "success_soft", "expired": "danger_soft",
                      "suspended": "warning_soft"}.get(sub.status, "neutral_soft")

        status_label = QLabel(status_text)
        status_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color(color_token)};"
            f"  background-color: {tm.color(soft_token)};"
            f"  border-radius: 10px;"
            f"  padding: 3px 10px;"
            f"  font-weight: 700;"
            f"  font-size: 11px;"
            f"}}"
        )
        title_row.addWidget(status_label)
        layout.addLayout(title_row)

        dates = QLabel(t("progress.hist.dates", start=sub.start_date, end=sub.expiry_date))
        dates.setStyleSheet(f"QLabel {{ color: {tm.color('text_secondary')}; font-size: 12px; }}")
        layout.addWidget(dates)

        used = sub.sessions_total - sub.sessions_remaining
        sessions = QLabel(t("progress.hist.sessions",
                            used=used, total=sub.sessions_total,
                            remaining=sub.sessions_remaining))
        sessions.setStyleSheet(f"QLabel {{ color: {tm.color('text_secondary')}; font-size: 12px; }}")
        layout.addWidget(sessions)

        if sub.payment_amount is not None and sub.payment_amount > 0:
            payment = QLabel(t("progress.hist.payment",
                               amount=f"{sub.payment_amount:,.0f}",
                               date=sub.payment_date or "—"))
            payment.setStyleSheet(f"QLabel {{ color: {tm.color('text_secondary')}; font-size: 12px; }}")
            layout.addWidget(payment)

        days = QLabel(t("progress.hist.days",
                        days=", ".join(t(f"weekday.{d.lower()}") for d in (sub.allowed_days or []))))
        days.setWordWrap(True)
        days.setStyleSheet(f"QLabel {{ color: {tm.color('text_secondary')}; font-size: 12px; }}")
        layout.addWidget(days)

        return card

    # ---------- timeline ----------

    def _render_timeline(self):
        self.timeline.clear()

        if not self._events:
            self.timeline.hide()
            self.timeline_empty.show()
            return

        self.timeline.show()
        self.timeline_empty.hide()

        tm = theme()
        groups = OrderedDict()
        for e in self._events:
            ym = e.when[:7]
            groups.setdefault(ym, []).append(e)

        for ym, events in groups.items():
            header = QListWidgetItem(self._month_header(ym))
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setForeground(QColor(tm.color("text_secondary")))
            self.timeline.addItem(header)

            for e in events:
                badge = self._kind_badge(e.kind)
                ts = e.when[:16]
                text = f"    {badge}   {ts}   ·   {e.summary}"
                item = QListWidgetItem(text)
                item.setForeground(QColor(tm.color("text")))
                self.timeline.addItem(item)

            self.timeline.addItem(QListWidgetItem(""))

    def _month_header(self, ym: str) -> str:
        try:
            year, month = ym.split("-")
            return f"── {t(MONTH_KEYS[int(month)-1])} {year} ──────────────────"
        except Exception:
            return f"── {ym} ──"

    def _kind_badge(self, kind: str) -> str:
        return {
            "attendance":   "🎟",
            "subscription": "📋",
            "payment":      "💵",
            "player":       "👤",
            "admin":        "⚙",
        }.get(kind, "•")

    # ---------- actions ----------

    def _on_print(self):
        if not (self._events or self._attendance):
            info(self, t("history.print_nothing_title"),
                 t("history.print_nothing_msg"))
            return

        from services.pdf_export import print_player_history
        from repositories import players_repo

        player = players_repo.get_by_id(self.player_id)
        if player is None:
            return

        print_player_history(
            parent_widget=self,
            player=player,
            attendance=self._attendance,
            active_subs=self._active_subs,
            all_subs=self._all_subs,
            timeline=self._events,
        )
    def _on_timeline_context_menu(self, pos):
        item = self.timeline.itemAt(pos)
        if not item:
            return
            
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or data.get("kind") != "payment":
            return
            
        from qtpy.QtWidgets import QMenu
        from qtpy.QtGui import QAction
        
        menu = QMenu(self)
        edit_act = QAction(t("payments.edit"), self)
        edit_act.triggered.connect(lambda: self._edit_payment(data["payment_id"]))
        menu.addAction(edit_act)
        
        del_act = QAction(t("payments.delete"), self)
        del_act.triggered.connect(lambda: self._delete_payment(data["payment_id"]))
        menu.addAction(del_act)
        
        menu.exec(self.timeline.mapToGlobal(pos))

    def _edit_payment(self, payment_id: int):
        # You'll need to create a small dialog for this, or reuse an existing one.
        # For now, we'll just show a message box as a placeholder.
        from ui.message_box import info
        info(self, "Edit Payment", "Edit dialog placeholder. (Payment ID: {})".format(payment_id))

    def _delete_payment(self, payment_id: int):
        from ui.message_box import ask, warn, info
        if not ask(self, t("payments.confirm_delete_title"), t("payments.confirm_delete_body")):
            return
        try:
            from repositories import payments_repo
            from services import audit_service
            # Log before deleting so we know what it was
            p = payments_repo.get_by_id(payment_id)
            if p:
                audit_service.record("payment.delete", target_type="payment", target_id=payment_id, details={"amount": p.amount})
            payments_repo.delete(payment_id)
            QTimer.singleShot(0, self.refresh)
        except Exception as e:
            warn(self, "Error", str(e))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    if not s:
        return date.today()
    s = s.strip()[:10]
    return date.fromisoformat(s)