"""
Audit log screen — v4 design.

Manager-only. Shows every recorded admin action, filtered by:
  * free-text search (username, action)
  * action type
  * user
  * date range
"""

import os
import sys
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QDateEdit, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import audit_repo
from ui.components import Toolbar, SectionCard, EmptyState
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING
from ui.i18n import t


class AuditScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._build_ui()
        self.refresh()
        self._init_theme()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        # ---- Toolbar with filters ----
        self.toolbar = Toolbar()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("audit.search_placeholder"))
        self.search_input.setProperty("cssClass", "search")
        self.search_input.setMinimumWidth(200)
        self.search_input.textChanged.connect(self.refresh)

        self.action_filter = QComboBox()
        self.action_filter.addItem(t("audit.filter.all_actions"), None)
        for code in audit_repo.distinct_actions():
            self.action_filter.addItem(self._friendly_action(code), code)
        self.action_filter.currentIndexChanged.connect(self.refresh)

        self.user_filter = QComboBox()
        self.user_filter.addItem(t("audit.filter.all_users"), None)
        for uname in audit_repo.distinct_usernames():
            self.user_filter.addItem(uname, uname)
        self.user_filter.currentIndexChanged.connect(self.refresh)

        # Date range — from / to, default = last 30 days
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.dateChanged.connect(self.refresh)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self.refresh)

        self.clear_button = QPushButton(t("audit.clear_filters"))
        make_secondary(self.clear_button)
        self.clear_button.clicked.connect(self._clear_filters)

        self.toolbar.add_leading(self.search_input, stretch=1)
        self.toolbar.add_leading(self.action_filter)
        self.toolbar.add_leading(self.user_filter)

        # Date filters on a second row
        date_row = QHBoxLayout()
        date_row.setSpacing(SPACING["sm"])
        date_row.addWidget(QLabel(t("audit.date_from")))
        date_row.addWidget(self.date_from)
        date_row.addWidget(QLabel(t("audit.date_to")))
        date_row.addWidget(self.date_to)
        date_row.addStretch()
        date_row.addWidget(self.clear_button)

        root.addWidget(self.toolbar)
        root.addLayout(date_row)

        # ---- Table card ----
        self.table_card = SectionCard(title=t("audit.title"))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            t("audit.col.when"),
            t("audit.col.user"),
            t("audit.col.action"),
            t("audit.col.target"),
            t("audit.col.details"),
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.table_card.body.addWidget(self.table)
        root.addWidget(self.table_card, stretch=1)

        # Empty state overlay (shown when table is empty)
        self.empty_state = EmptyState(
            icon="🗒",
            message=t("audit.empty"),
        )

    # ---------- theming ----------

    def restyle(self):
        # Audit rows use tokens for text color; refresh on theme change
        if hasattr(self, "_entries"):
            self._render_rows(self._entries)

    # ---------- data ----------

    def refresh(self):
        search = self.search_input.text().strip()
        action = self.action_filter.currentData()
        username = self.user_filter.currentData()

        d_from = self.date_from.date()
        d_to = self.date_to.date()
        date_from = f"{d_from.year():04d}-{d_from.month():02d}-{d_from.day():02d}"
        date_to = f"{d_to.year():04d}-{d_to.month():02d}-{d_to.day():02d}"

        entries = audit_repo.query(
            search=search,
            action=action,
            username=username,
            date_from=date_from,
            date_to=date_to,
            limit=500,
        )
        self._entries = entries
        self._render_rows(entries)

    def _clear_filters(self):
        self.search_input.setText("")
        self.action_filter.setCurrentIndex(0)
        self.user_filter.setCurrentIndex(0)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_to.setDate(QDate.currentDate())

    def _render_rows(self, entries):
        self.table.setRowCount(len(entries))
        tm = theme()

        for i, e in enumerate(entries):
            # When
            when = e.created_at or ""
            self.table.setItem(i, 0, QTableWidgetItem(when))

            # User
            self.table.setItem(i, 1, QTableWidgetItem(e.username))

            # Action — friendly label
            self.table.setItem(i, 2, QTableWidgetItem(self._friendly_action(e.action)))

            # Target — "player #42"
            target = ""
            if e.target_type and e.target_id:
                target = f"{e.target_type} #{e.target_id}"
            elif e.target_type:
                target = e.target_type
            self.table.setItem(i, 3, QTableWidgetItem(target))

            # Details — compact JSON-ish string
            details_str = ""
            if e.details:
                d = e.details_dict()
                parts = []
                for k, v in d.items():
                    parts.append(f"{k}={v}")
                details_str = " · ".join(parts)
            detail_item = QTableWidgetItem(details_str)
            detail_item.setForeground(QColor(tm.color("text_secondary")))
            self.table.setItem(i, 4, detail_item)

    def _friendly_action(self, code: str) -> str:
        """Map an action code to a translation key. Falls back to the
        raw code if no translation exists."""
        key = f"audit.action.{code}"
        translated = t(key)
        return translated if translated != key else code