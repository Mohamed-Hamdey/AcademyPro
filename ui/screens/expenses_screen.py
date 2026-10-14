"""
Expenses management screen — v4 design.

Manager-only. Shows all expenses with a month filter, plus Add/Edit/Delete
actions and a per-category breakdown.
"""

import os
import sys
import calendar
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QScrollArea,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import expense_service
from ui.components import SectionCard, Toolbar, EmptyState, KpiCard
from ui.dialogs.expense_form_dialog import ExpenseFormDialog
from ui.theme import theme, ThemedWidget, make_secondary, make_danger
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.message_box import warn, ask


MONTH_KEYS = [
    "month.january", "month.february", "month.march", "month.april",
    "month.may", "month.june", "month.july", "month.august",
    "month.september", "month.october", "month.november", "month.december",
]


class ExpensesScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._selected_year = date.today().year
        self._selected_month = date.today().month
        self._rows = []
        self._build_ui()
        self.refresh()
        self._init_theme()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        # Toolbar
        self.toolbar = Toolbar()

        self.month_selector = QComboBox()
        # Last 12 months
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

        self.add_button = QPushButton(t("expenses.add"))
        self.add_button.clicked.connect(self._on_add)

        self.toolbar.add_leading(QLabel(t("expenses.filter.month")))
        self.toolbar.add_leading(self.month_selector)
        self.toolbar.add_trailing(self.add_button)
        root.addWidget(self.toolbar)

        # KPI cards
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(SPACING["md"])
        self.total_card = KpiCard(t("expenses.kpi.total"), "0")
        self.count_card = KpiCard(t("expenses.kpi.count"), "0")
        self.top_card   = KpiCard(t("expenses.kpi.top_category"), "—")
        for c in (self.total_card, self.count_card, self.top_card):
            kpi_row.addWidget(c, stretch=1)
        root.addLayout(kpi_row)

        # Content scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(SPACING["lg"])

        # Table card
        self.table_card = SectionCard(title=t("expenses.list.title"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            t("expenses.col.date"),
            t("expenses.col.category"),
            t("expenses.col.description"),
            t("expenses.col.amount"),
        ])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setMinimumHeight(180)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.cellDoubleClicked.connect(lambda *_: self._on_edit())
        self.table_card.body.addWidget(self.table)

        self.table_empty = EmptyState(
            icon="💸", message=t("expenses.list.empty"),
        )
        self.table_empty.hide()
        self.table_card.body.addWidget(self.table_empty)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACING["sm"])
        self.edit_button = QPushButton(t("expenses.action.edit"))
        make_secondary(self.edit_button)
        self.edit_button.clicked.connect(self._on_edit)
        self.edit_button.setEnabled(False)

        self.delete_button = QPushButton(t("expenses.action.delete"))
        make_danger(self.delete_button)
        self.delete_button.clicked.connect(self._on_delete)
        self.delete_button.setEnabled(False)

        btn_row.addWidget(self.edit_button)
        btn_row.addWidget(self.delete_button)
        btn_row.addStretch()
        self.table_card.body.addLayout(btn_row)

        body.addWidget(self.table_card)

        # Category breakdown
        self.breakdown_card = SectionCard(title=t("expenses.breakdown.title"))
        self.breakdown_list = QVBoxLayout()
        self.breakdown_list.setSpacing(SPACING["xs"])
        self.breakdown_card.body.addLayout(self.breakdown_list)
        body.addWidget(self.breakdown_card)

        body.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    # ---------- theming ----------

    def restyle(self):
        tm = theme()
        self._style_kpi(self.total_card, tm.color("danger"))
        self._style_kpi(self.count_card, tm.color("text"))
        self._style_kpi(self.top_card,   tm.color("warning"))
        if self._rows is not None:
            self._render()

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

    # ---------- data ----------

    def _on_month_changed(self, _idx):
        y, m = self._month_options[self.month_selector.currentIndex()]
        self._selected_year = y
        self._selected_month = m
        self.refresh()

    def refresh(self):
        self._rows = expense_service.list_for_month(
            self._selected_year, self._selected_month
        )
        self._render()

    def _render(self):
        # KPIs
        total = sum(e.amount for e in self._rows)
        count = len(self._rows)
        by_cat = expense_service.total_by_category_for_month(
            self._selected_year, self._selected_month
        )
        top_cat_key = by_cat[0]["category"] if by_cat else None
        top_cat_label = t(f"expenses.cat.{top_cat_key}") if top_cat_key else "—"
        top_cat_amount = f"{by_cat[0]['total']:,.0f} EGP" if by_cat else ""

        self.total_card.set_value(f"{total:,.0f} EGP")
        self.total_card.set_subtitle(t("expenses.kpi.total_sub"))
        self.count_card.set_value(str(count))
        self.count_card.set_subtitle(t("expenses.kpi.count_sub"))
        self.top_card.set_value(top_cat_amount or "—")
        self.top_card.set_subtitle(top_cat_label)

        # Table
        self.table.setRowCount(len(self._rows))
        tm = theme()
        for i, e in enumerate(self._rows):
            self.table.setItem(i, 0, QTableWidgetItem(e.expense_date))
            self.table.setItem(i, 1, QTableWidgetItem(t(f"expenses.cat.{e.category}")))
            self.table.setItem(i, 2, QTableWidgetItem(e.description))
            amt_item = QTableWidgetItem(f"{e.amount:,.0f} {e.currency}")
            amt_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            amt_item.setForeground(QColor(tm.color("danger")))
            self.table.setItem(i, 3, amt_item)

        # Toggle table/empty
        if self._rows:
            self.table.show()
            self.table_empty.hide()
        else:
            self.table.hide()
            self.table_empty.show()

        self._update_actions()

        # Breakdown
        while self.breakdown_list.count():
            item = self.breakdown_list.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not by_cat:
            self.breakdown_card.hide()
        else:
            self.breakdown_card.show()
            for row in by_cat:
                line = QHBoxLayout()
                name = QLabel(t(f"expenses.cat.{row['category']}"))
                name.setStyleSheet(
                    f"QLabel {{ color: {tm.color('text')}; font-size: 13px; }}"
                )
                amount = QLabel(f"{row['total']:,.0f} EGP   ({row['count']})")
                amount.setStyleSheet(
                    f"QLabel {{ color: {tm.color('text_secondary')}; font-size: 13px; }}"
                )
                amount.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                line.addWidget(name)
                line.addStretch()
                line.addWidget(amount)
                wrap = QWidget()
                wrap.setLayout(line)
                self.breakdown_list.addWidget(wrap)

    def _selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._rows):
            return self._rows[idx]
        return None

    def _update_actions(self):
        has = self._selected() is not None
        self.edit_button.setEnabled(has)
        self.delete_button.setEnabled(has)

    # ---------- actions ----------

    def _on_add(self):
        dlg = ExpenseFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _on_edit(self):
        e = self._selected()
        if e is None:
            return
        dlg = ExpenseFormDialog(expense=e, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_delete(self):
        e = self._selected()
        if e is None:
            return
        if not ask(self, t("expenses.confirm.delete_title"),
                   t("expenses.confirm.delete_msg",
                     description=e.description, amount=f"{e.amount:,.0f}")):
            return
        expense_service.delete(e.expense_id)
        try:
            from services import audit_service
            audit_service.record(
                "expense.delete",
                target_type="expense",
                target_id=e.expense_id,
                details={"amount": e.amount},
            )
        except Exception:
            pass
        self.refresh()