"""
Player list screen — v4 design.

Layout:
    ┌──────────────────────────────────────────────────────────┐
    │  [search …] [Plan ▾] [Status ▾]              [+ Add]      │  ← Toolbar
    │                                                          │
    │  ┌─ Players (table) ─────────────────────────────────────┐│
    │  │  ID   Name   Plan   Sessions   Status                  ││
    │  │  ...                                                   ││
    │  └───────────────────────────────────────────────────────┘│
    │                                                          │
    │  (empty state shown instead of the table when no rows)    │
    └──────────────────────────────────────────────────────────┘

The screen no longer carries its own page title; the workspace header
shows it (see ui/main_window.py + ui/shell.py).
"""

import os
import sys

from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget,
    QComboBox, QLabel,
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import load_config, get_plan_label
from repositories import players_repo
from services import subscription_service
from ui.dialogs.player_form_dialog import PlayerFormDialog
from ui.screens.player_detail_screen import PlayerDetailScreen
from ui.dialogs.qr_preview_dialog import QRPreviewDialog
from ui.components import Toolbar, EmptyState, Pill
from ui.theme import theme, ThemedWidget
from ui.design import SPACING, RADIUS
from ui.i18n import t


_STATUS_KEY = {
    "active":    "players.status.active",
    "expired":   "players.status.expired",
    "suspended": "players.status.suspended",
    "none":      "players.status.none",
}


class PlayerListScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._loaded = False
        self._build_ui()
        # Deferred to first show — see showEvent.
        self._init_theme()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self.refresh()

    def _build_ui(self):
        self.stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stack)

        # ----- List page -----
        list_page = QWidget()
        page_layout = QVBoxLayout(list_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(SPACING["lg"])

        # ---- Toolbar: search + filters + add button ----
        self.toolbar = Toolbar()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("players.search.placeholder"))
        self.search_input.setProperty("cssClass", "search")
        self.search_input.setMinimumWidth(240)
        self.search_input.textChanged.connect(self.refresh)

        config = load_config()

        self.plan_filter = QComboBox()
        self.plan_filter.addItem(t("players.filter.all_plans"), None)
        for key, plan in config["plans"].items():
            self.plan_filter.addItem(get_plan_label(key), key)
        self.plan_filter.currentIndexChanged.connect(self.refresh)

        self.status_filter = QComboBox()
        self.status_filter.addItem(t("players.filter.all_statuses"), None)
        for key in ("active", "expired", "suspended", "none"):
            self.status_filter.addItem(t(_STATUS_KEY[key]), key)
        self.status_filter.currentIndexChanged.connect(self.refresh)

        self.add_button = QPushButton(t("players.add_player"))
        self.add_button.clicked.connect(self._on_add_player)

        self.toolbar.add_leading(self.search_input, stretch=1)
        self.toolbar.add_leading(self.plan_filter)
        self.toolbar.add_leading(self.status_filter)
        self.toolbar.add_trailing(self.add_button)

        page_layout.addWidget(self.toolbar)

        # ---- Table (or empty state, swapped by visibility) ----
        self.table_container = QWidget()
        table_layout = QVBoxLayout(self.table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            t("players.col.id"),
            t("players.col.name"),
            t("players.col.plan"),
            t("players.col.sessions"),
            t("players.col.status"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        table_layout.addWidget(self.table)

        # Empty state — hidden by default, shown when there are no rows
        self.empty_state = EmptyState(
            icon="👥",
            message=t("players.empty"),
            action_text=t("players.add_player"),
            on_action=self._on_add_player,
        )
        self.empty_state.hide()
        table_layout.addWidget(self.empty_state, stretch=1)

        page_layout.addWidget(self.table_container, stretch=1)

        self.stack.addWidget(list_page)
        self.stack.setCurrentIndex(0)

    # ---------- theme ----------

    def restyle(self):
        if hasattr(self, "_status_items"):
            self._repaint_status_items()

    def _repaint_status_items(self):
        tm = theme()
        token_colors = {
            "active":    tm.color("success"),
            "expired":   tm.color("danger"),
            "suspended": tm.color("warning"),
            "none":      tm.color("text_secondary"),
        }
        soft_bg = {
            "active":    tm.color("success_soft"),
            "expired":   tm.color("danger_soft"),
            "suspended": tm.color("warning_soft"),
            "none":      tm.color("neutral_soft"),
        }
        for item, kind in self._status_items:
            item.setForeground(QColor(token_colors[kind]))
            item.setBackground(QColor(soft_bg[kind]))

    # ---------- data ----------

    def refresh(self):
        search_text = self.search_input.text().strip()
        players = players_repo.search_by_name(search_text) if search_text else players_repo.list_all()

        plan_filter = self.plan_filter.currentData()
        status_filter = self.status_filter.currentData()

        # Batch fetch statuses — one DB call instead of N.
        player_ids = [p.player_id for p in players]
        statuses = subscription_service.get_display_status_bulk(player_ids)

        rows = []
        for player in players:
            display = statuses.get(player.player_id, {"status": "none", "plan_type": None})
            if plan_filter and display["plan_type"] != plan_filter:
                continue
            if status_filter and display["status"] != status_filter:
                continue
            rows.append((player, display))

        self._render_rows(rows)

    def _render_rows(self, rows):
        if not rows:
            self.table.hide()
            self.empty_state.show()
            self._current_rows = []
            self._status_items = []
            return

        self.table.show()
        self.empty_state.hide()

        self.table.setRowCount(len(rows))
        self._current_rows = [player for player, _ in rows]
        self._status_items = []

        tm = theme()
        for i, (player, display) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(player.player_id)))
            self.table.setItem(i, 1, QTableWidgetItem(player.full_name))
            if display["plan_type"]:
                self.table.setItem(i, 2, QTableWidgetItem(get_plan_label(display["plan_type"])))
                self.table.setItem(
                    i, 3,
                    QTableWidgetItem(f"{display['sessions_remaining']}/{display['sessions_total']}")
                )
            else:
                dash = t("players.col.dash")
                self.table.setItem(i, 2, QTableWidgetItem(dash))
                self.table.setItem(i, 3, QTableWidgetItem(dash))

            status_item = QTableWidgetItem(t(_STATUS_KEY.get(display["status"], "players.status.none")))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 4, status_item)
            self._status_items.append((status_item, display["status"]))

        self._repaint_status_items()

    # ---------- actions ----------

    def _on_add_player(self):
        dialog = PlayerFormDialog(parent=self)
        if dialog.exec():
            self.refresh()
            qr_path = getattr(dialog, "newly_created_qr_path", None)
            if qr_path:
                name = dialog.name_input.text().strip()
                preview = QRPreviewDialog(name, dialog.saved_player_id, qr_path, parent=self)
                preview.exec()

    def _on_row_double_clicked(self, row: int, column: int):
        player = self._current_rows[row]
        self._open_detail(player.player_id)

    def _open_detail(self, player_id: int):
        detail = PlayerDetailScreen(player_id, on_back=self._close_detail, parent=self)
        self.stack.addWidget(detail)
        self.stack.setCurrentWidget(detail)

    def _close_detail(self):
        current = self.stack.currentWidget()
        self.stack.setCurrentIndex(0)
        self.stack.removeWidget(current)
        current.deleteLater()
        self.refresh()