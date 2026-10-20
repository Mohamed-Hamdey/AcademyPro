"""
Player list screen — v3 redesign.

Layout (top to bottom):
  1. Toolbar: search | plan filter | status filter | [+ Add Player]
  2. Activity tabs: [All (N)] [Kung Fu (N)] [Karate (N)] ...
  3. Summary strip: Active | Expired | Suspended | Expiring | Low sessions
  4. Table: Name+ID | Activity pills | Plan | Sessions bar | Expires | Status
  5. Footer: "Showing X of Y players"

Sorting: default = needs-attention first (expired / expiring soon),
then name. Column headers are clickable and toggle ascending/descending.

Rows for suspended/expired players are dimmed, not hidden.
"""

import os
import sys
import logging
from datetime import date, datetime

from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget,
    QComboBox, QLabel, QFrame, QSizePolicy, QAbstractItemView,
    QMenu, QButtonGroup, QScrollArea, QStyledItemDelegate,
)
from qtpy.QtCore import Qt, QSettings, QSize, QRectF, QModelIndex,QTimer
from qtpy.QtGui import QColor, QPainter, QFont, QFontMetrics, QBrush, QPen, QIcon

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import load_config, get_plan_label
from repositories import players_repo
from services import subscription_service, activity_service
from ui.dialogs.player_form_dialog import PlayerFormDialog
from ui.screens.player_detail_screen import PlayerDetailScreen
from ui.dialogs.qr_preview_dialog import QRPreviewDialog
from ui.components import  EmptyState, Toolbar, PillDelegate
from ui.theme import theme, ThemedWidget
from ui.design import SPACING, RADIUS, TYPOGRAPHY
from ui.i18n import t


_STATUS_KEY = {
    "active":    "players.status.active",
    "expired":   "players.status.expired",
    "suspended": "players.status.suspended",
    "none":      "players.status.none",
}

_STATUS_PILL_KIND = {
    "active":    "success",
    "expired":   "danger",
    "suspended": "warning",
    "none":      "neutral",
}

_SETTINGS_ORG = "MembershipSystem"
_SETTINGS_APP = "app"
_LAST_TAB_KEY = "players/last_activity_tab"





class SessionsBarDelegate(QStyledItemDelegate):
    """
    Draws a compact progress bar + "N/M" text.

    Expects the cell's QTableWidgetItem to have data(UserRole) set to
    a dict: {"remaining": int, "total": int}.
    """

    def paint(self, painter, option, index):
        data = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            super().paint(painter, option, index)
            return

        remaining = data.get("remaining", 0) or 0
        total = data.get("total", 0) or 0

        tm = theme()

        # Bar color by urgency
        if remaining == 0:
            fill_color = tm.color("danger")
        elif remaining <= 1:
            fill_color = tm.color("warning")
        else:
            fill_color = tm.color("success")

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        r = option.rect
        pad_x = 12
        pad_y = 6
        inner_x = r.x() + pad_x
        inner_w = r.width() - pad_x * 2

        # Layout: text on top (row 1), bar on bottom (row 2)
        text_h = 14
        bar_h = 5
        gap = 4
        total_h = text_h + gap + bar_h
        start_y = r.y() + (r.height() - total_h) // 2

        # ---- Text row ----
        # Use pixel size only — see PillDelegate above for rationale.
        font = QFont(option.font)
        base_px = font.pixelSize()
        if base_px <= 0:
            base_px = 13
        font.setPixelSize(max(9, int(base_px * 0.85)))
        font.setBold(True)
        painter.setFont(font)

        text_rect = QRectF(
            inner_x, start_y, inner_w, text_h
        )
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{remaining} / {total}",
        )

        # ---- Bar row (below) ----
        bar_y = start_y + text_h + gap

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tm.color("surface_alt")))
        painter.drawRoundedRect(
            QRectF(inner_x, bar_y, inner_w, bar_h),
            bar_h / 2, bar_h / 2,
        )

        # Fill
        if total > 0:
            frac = max(0.02, remaining / total)
            fill_w = inner_w * frac
            painter.setBrush(QColor(fill_color))
            painter.drawRoundedRect(
                QRectF(inner_x, bar_y, fill_w, bar_h),
                bar_h / 2, bar_h / 2,
            )

        painter.restore()


# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------

class PlayerListScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._loaded = False
        self._rows = []                # list[dict] — current table data
        self._current_activity_id = None
        self._sort_col = -1
        self._sort_asc = True

        self._build_ui()
        self._init_theme()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            # Defer the heavy rendering until the window has fully drawn
            QTimer.singleShot(0, self._initial_load)

    def _initial_load(self):
        try:
            self.refresh()
        except Exception:
            self._loaded = False
            raise

    # ---------- UI construction ----------

    def _build_ui(self):
        self.stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stack)

        # ---- Main page ----
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(SPACING["md"])

        # ---- Toolbar row ----
        self.toolbar = Toolbar()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("players.search.placeholder"))
        self.search_input.setProperty("cssClass", "search")
        self.search_input.setMinimumWidth(240)
        self.search_input.textChanged.connect(self._on_search_changed)

        # Debounce
        from ui.utils import Debouncer
        self._search_debouncer = Debouncer(250, self.refresh, parent=self)
        self.search_input.textChanged.connect(self._search_debouncer.trigger)

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

        # ---- Activity tabs (segmented control) ----
        self.tabs_container = QScrollArea()
        self.tabs_container.setWidgetResizable(True)
        self.tabs_container.setFrameShape(QFrame.Shape.NoFrame)
        self.tabs_container.setMaximumHeight(56)
        self.tabs_container.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        tabs_widget = QWidget()
        tabs_layout = QHBoxLayout(tabs_widget)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(SPACING["xs"])

        self._tab_buttons = []       # list of (button, activity_id or None)
        tabs_layout.addStretch()      # trailing stretch pushes tabs left

        tabs_widget.setLayout(tabs_layout)
        self.tabs_container.setWidget(tabs_widget)
        self._tabs_layout = tabs_layout
        self._tabs_widget = tabs_widget

        page_layout.addWidget(self.tabs_container)

        # ---- Summary strip ----
        self.summary_widget = QWidget()
        summary_layout = QHBoxLayout(self.summary_widget)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(SPACING["sm"])
        self._summary_labels = {}
        for key in ("active", "expired", "suspended", "expiring_soon", "low_sessions"):
            box = QFrame()
            box.setObjectName("summaryBox")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(10, 6, 10, 6)
            box_layout.setSpacing(2)
            lbl_title = QLabel(t(f"players.summary.{key}"))
            lbl_value = QLabel("0")
            box_layout.addWidget(lbl_title)
            box_layout.addWidget(lbl_value)
            self._summary_labels[key] = (lbl_title, lbl_value)
            summary_layout.addWidget(box, stretch=1)
        page_layout.addWidget(self.summary_widget)

        # ---- Table ----
        self.table_card = QFrame()
        self.table_card.setObjectName("playerTableCard")
        table_layout = QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            t("players.col.name"),
            t("players.col.activity"),
            t("players.col.plan"),
            t("players.col.sessions"),
            t("players.col.expires"),
            t("players.col.status"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(3, 120)
        
        # Expires column needs more room for "2026-10-29 (3 days)"
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(4, 200)
        
        # Status column
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(5, 170)
        self.table.horizontalHeader().setMinimumSectionSize(100)


        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        # Sorting is handled in _refresh_table so the displayed rows and self._rows
        # always stay in the same order (Qt's automatic item sorting can desync them).
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)

        # Delegates
        self._pill_delegate = PillDelegate(self.table)
        self._sessions_delegate = SessionsBarDelegate(self.table)
        self.table.setItemDelegateForColumn(5, self._pill_delegate)   # Status
        self.table.setItemDelegateForColumn(3, self._sessions_delegate)  # Sessions

        table_layout.addWidget(self.table)

        # ---- Footer ----
        footer = QHBoxLayout()
        footer.setContentsMargins(8, 4, 8, 4)
        self.footer_label = QLabel("")
        footer.addWidget(self.footer_label)
        footer.addStretch()
        table_layout.addLayout(footer)

        page_layout.addWidget(self.table_card, stretch=1)

        # ---- Empty state ----
        self.empty_state = EmptyState(
            icon="👥",
            message=t("players.empty"),

        )
        self.empty_state.hide()
        page_layout.addWidget(self.empty_state, stretch=1)

        self.stack.addWidget(page)
        self.stack.setCurrentIndex(0)

    # ---------- activity tabs ----------

    def _reload_activity_tabs(self):
        # Clear existing tab buttons
        for btn, _ in self._tab_buttons:
            btn.setParent(None)
            btn.deleteLater()
        self._tab_buttons = []

        # Fetch fresh data
        counts = players_repo.list_activity_counts()
        activities = activity_service.list_active()
        all_count = len(players_repo.list_with_details())

        # "All" tab
        self._add_tab_button(None, t("players.tab.all"), all_count, primary=True)

        # One tab per activity
        for act in activities:
            count = counts.get(act.activity_id, 0)
            name = activity_service.get_localized_name(act)
            self._add_tab_button(act.activity_id, name, count)

        # Restore last-selected tab
        settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        saved_id = settings.value(_LAST_TAB_KEY, None)
        try:
            saved_id = int(saved_id) if saved_id not in (None, "", "None") else None
        except (ValueError, TypeError):
            saved_id = None

        # Select it, or default to "All"
        for btn, act_id in self._tab_buttons:
            if act_id == saved_id:
                btn.setChecked(True)
                self._current_activity_id = act_id
                break
        else:
            # No match, select All
            if self._tab_buttons:
                self._tab_buttons[0][0].setChecked(True)
                self._current_activity_id = None

    def _add_tab_button(self, activity_id, label, count, primary=False):
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setProperty("tabPill", "true")
        btn.setText(f"{label}  ({count})")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _, a=activity_id: self._on_tab_clicked(a))
        self._tabs_layout.insertWidget(
            self._tabs_layout.count() - 1, btn
        )
        self._tab_buttons.append((btn, activity_id))
        return btn

    def _on_tab_clicked(self, activity_id):
        # Uncheck all except the one clicked
        for btn, a in self._tab_buttons:
            btn.setChecked(a == activity_id)

        self._current_activity_id = activity_id

        # Persist to QSettings
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue(_LAST_TAB_KEY, "" if activity_id is None else activity_id)

        self.refresh()

    # ---------- search / filter handlers ----------

    def _on_search_changed(self, _text):
        # The debouncer handles the actual refresh.
        pass

    # ---------- data load ----------

    def refresh(self):
        """Reload the table based on current tab, search, and filters."""
        self._refresh_summary()
        self._refresh_table()

    def _refresh_summary(self):
        if self._current_activity_id is None:
            counts = players_repo.count_by_status()
        else:
            counts = players_repo.count_by_status_for_activity(self._current_activity_id)

        for key, (title_lbl, val_lbl) in self._summary_labels.items():
            val_lbl.setText(str(counts.get(key, 0)))

        self._style_summary()

    def _render_rows(self, rows):
        prev_player_id = None
        selected = self.table.selectionModel().selectedRows() if self._rows else []
        if selected:
            prev_idx = selected[0].row()
            if 0 <= prev_idx < len(self._rows):
                prev_player_id = self._rows[prev_idx]["player"].player_id

        if not rows:
            self.table_card.hide()
            self.empty_state.show()
            self.footer_label.setText("")
            return

        self.table_card.show()
        self.table.show()
        self.empty_state.hide()

        tm = theme()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            player = row["player"]
            status = row["status"]

            name_text = player.full_name or "?"
            name_item = QTableWidgetItem(name_text)
            name_item.setToolTip(f"{name_text} · ID: {player.player_id}")
            name_item.setData(Qt.ItemDataRole.UserRole, player.player_id)
            if status in ("suspended", "expired", "none"):
                name_item.setForeground(QColor(tm.color("text_secondary")))
            self.table.setItem(i, 0, name_item)

            act_text = ", ".join(row["activity_names"]) if row["activity_names"] else "—"
            act_item = QTableWidgetItem(act_text)
            self.table.setItem(i, 1, act_item)

            plan_text = (
                get_plan_label(row["plan_label"])
                if row["plan_label"] and row["plan_label"] != ""
                else "—"
            )
            plan_item = QTableWidgetItem(plan_text)
            self.table.setItem(i, 2, plan_item)

            sessions_item = QTableWidgetItem()
            if row["sessions_total"] is not None:
                sessions_item.setData(Qt.ItemDataRole.UserRole, {
                    "remaining": row["sessions_remaining"] or 0,
                    "total": row["sessions_total"] or 0,
                })
            self.table.setItem(i, 3, sessions_item)

            # ---- Expires (Now reads clearly) ----
            if row["expiry_date"] and row["days_left"] is not None:
                days = row["days_left"]
                if days < 0:
                    exp_text = f"{row['expiry_date']} ({t('players.expired_days_ago', n=-days)})"
                elif days == 0:
                    exp_text = f"{row['expiry_date']} ({t('players.expires_today')})"
                elif days <= 7:
                    exp_text = f"{row['expiry_date']} ({t('players.expires_in_days', n=days)})"
                else:
                    exp_text = row["expiry_date"]
            else:
                exp_text = "—"
            exp_item = QTableWidgetItem(exp_text)
            self.table.setItem(i, 4, exp_item)

            status_item = QTableWidgetItem()
            status_item.setData(Qt.ItemDataRole.UserRole, {
                "text": t(_STATUS_KEY.get(status, "players.status.none")),
                "kind": _STATUS_PILL_KIND.get(status, "neutral"),
            })
            self.table.setItem(i, 5, status_item)

            if status in ("expired", "suspended"):
                for c in range(6):
                    item = self.table.item(i, c)
                    if item is not None:
                        item.setForeground(QColor(tm.color("text_secondary")))

        total_count = len(rows)
        self.footer_label.setText(t("players.footer.showing", n=total_count))
        self._style_footer()

        if prev_player_id is not None:
            for i, row in enumerate(rows):
                if row["player"].player_id == prev_player_id:
                    self.table.selectRow(i)
                    break

    def _refresh_table(self):
        search_text = self.search_input.text().strip()

        # Fetch rows from the repo.
        try:
            if self._current_activity_id is None:
                if search_text:
                    rows = players_repo.search_with_details(search_text)
                else:
                    rows = players_repo.list_with_details()
            else:
                if search_text:
                    rows = players_repo.search_with_details_for_activity(
                        self._current_activity_id, search_text
                    )
                else:
                    rows = players_repo.list_with_details_for_activity(
                        self._current_activity_id
                    )
        except Exception:
            logging.getLogger(__name__).exception("Failed to load player rows")
            rows = []

        # Apply plan/status filters
        plan_filter = self.plan_filter.currentData()
        status_filter = self.status_filter.currentData()

        filtered = []
        for row in rows:
            if plan_filter and row["plan_label"] != plan_filter:
                continue
            if status_filter and row["status"] != status_filter:
                continue
            filtered.append(row)

        # Sort: needs-attention first, then by name (or by chosen sort column)
        if self._sort_col < 0:
            # Default sort
            filtered.sort(key=self._default_sort_key)
        else:
            # User-chosen sort
            reverse = not self._sort_asc
            filtered.sort(
                key=lambda r: self._sort_key(r, self._sort_col),
                reverse=reverse,
            )

        self._rows = filtered
        self._render_rows(filtered)

    def _default_sort_key(self, row):
        # Priority: expired (0) > expiring soon (1) > low sessions (2) > active (3) > none (4)
        status = row["status"]
        days = row["days_left"]
        remaining = row["sessions_remaining"]

        if status == "expired":
            priority = 0
        elif status == "active" and days is not None and days <= 7:
            priority = 1
        elif status == "active" and remaining is not None and remaining <= 1:
            priority = 2
        elif status == "active":
            priority = 3
        else:
            priority = 4

        return (priority, row["player"].full_name.lower())

    def _on_header_clicked(self, column: int):
        """Sort by a clicked column; clicking it again reverses the direction."""
        if column == self._sort_col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = column
            self._sort_asc = True

        order = (
            Qt.SortOrder.AscendingOrder
            if self._sort_asc
            else Qt.SortOrder.DescendingOrder
        )
        self.table.horizontalHeader().setSortIndicator(column, order)
        self.refresh()

    def _sort_key(self, row, col):
        if col == 0:
            return row["player"].full_name.lower()
        if col == 1:
            return " ".join(row["activity_names"]).lower()
        if col == 2:
            return row["plan_label"].lower()
        if col == 3:
            return row["sessions_remaining"] or 0
        if col == 4:
            return row["expiry_date"] or ""
        if col == 5:
            return row["status"]
        return ""

    # ---------- render ----------

    def _render_rows(self, rows):
        # Capture current selection before we blow away the table.
        prev_player_id = None
        selected = self.table.selectionModel().selectedRows() if self._rows else []
        if selected:
            prev_idx = selected[0].row()
            if 0 <= prev_idx < len(self._rows):
                prev_player_id = self._rows[prev_idx]["player"].player_id

        if not rows:
            # The empty state replaces the table card instead of appearing below
            # an empty table, which otherwise leaves a large blank panel on screen.
            self.table_card.hide()
            self.empty_state.show()
            self.footer_label.setText("")
            return

        self.table_card.show()
        self.table.show()
        self.empty_state.hide()

        tm = theme()

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            player = row["player"]
            status = row["status"]

            # ---- Name column: "Name" + small "(ID)" ----
            name_text = player.full_name or "?"
            if status in ("suspended", "expired"):
                name_text = name_text  # dimming handled below
            name_item = QTableWidgetItem(name_text)
            name_item.setToolTip(f"{name_text} · ID: {player.player_id}")
            name_item.setData(Qt.ItemDataRole.UserRole, player.player_id)
            if status in ("suspended", "expired", "none"):
                name_item.setForeground(QColor(tm.color("text_secondary")))
            self.table.setItem(i, 0, name_item)

            # ---- Activity pills ----
            act_text = ", ".join(row["activity_names"]) if row["activity_names"] else "—"
            act_item = QTableWidgetItem(act_text)
            self.table.setItem(i, 1, act_item)

            # ---- Plan ----
            plan_text = (
                get_plan_label(row["plan_label"])
                if row["plan_label"] and row["plan_label"] != ""
                else "—"
            )
            plan_item = QTableWidgetItem(plan_text)
            self.table.setItem(i, 2, plan_item)

            # ---- Sessions bar (delegate) ----
            sessions_item = QTableWidgetItem()
            if row["sessions_total"] is not None:
                sessions_item.setData(Qt.ItemDataRole.UserRole, {
                    "remaining": row["sessions_remaining"] or 0,
                    "total": row["sessions_total"] or 0,
                })
            self.table.setItem(i, 3, sessions_item)

            # ---- Expires ----
            if row["expiry_date"] and row["days_left"] is not None:
                days = row["days_left"]
                if days < 0:
                    exp_text = f"{row['expiry_date']}  ({t('players.expired_days_ago', n=-days)})"
                elif days == 0:
                    exp_text = f"{row['expiry_date']}  ({t('players.expires_today')})"
                elif days <= 7:
                    exp_text = f"{row['expiry_date']}  ({t('players.expires_in_days', n=days)})"
                else:
                    exp_text = row["expiry_date"]
            else:
                exp_text = "—"
            exp_item = QTableWidgetItem(exp_text)
            self.table.setItem(i, 4, exp_item)

            # ---- Status pill (delegate) ----
            status_item = QTableWidgetItem()
            status_item.setData(Qt.ItemDataRole.UserRole, {
                "text": t(_STATUS_KEY.get(status, "players.status.none")),
                "kind": _STATUS_PILL_KIND.get(status, "neutral"),
            })
            self.table.setItem(i, 5, status_item)

            # ---- Dim the whole row for expired/suspended ----
            if status in ("expired", "suspended"):
                for c in range(6):
                    item = self.table.item(i, c)
                    if item is not None:
                        item.setForeground(QColor(tm.color("text_secondary")))

        # ---- Footer ----
        total_count = len(rows)
        self.footer_label.setText(
            t("players.footer.showing", n=total_count)
        )
        self._style_footer()

        # ---- Restore selection if possible ----
        if prev_player_id is not None:
            for i, row in enumerate(rows):
                if row["player"].player_id == prev_player_id:
                    self.table.selectRow(i)
                    break

    # ---------- styling ----------

    def _style_summary(self):
        tm = theme()
        for key, (title_lbl, val_lbl) in self._summary_labels.items():
            color_token = {
                "active":         "success",
                "expired":        "danger",
                "suspended":      "warning",
                "expiring_soon":  "warning",
                "low_sessions":   "danger",
            }.get(key, "text")
            title_lbl.setStyleSheet(
                f"QLabel {{ color: {tm.color('text_secondary')};"
                f" background: transparent; font-size: 11px; font-weight: 600; }}"
            )
            val_lbl.setStyleSheet(
                f"QLabel {{ color: {tm.color(color_token)};"
                f" background: transparent; font-size: 18px; font-weight: 700; }}"
            )

        for box in self.summary_widget.findChildren(QFrame, "summaryBox"):
            box.setStyleSheet(
                f"QFrame#summaryBox {{"
                f"  background-color: {tm.color('surface')};"
                f"  border: 1px solid {tm.color('border')};"
                f"  border-radius: 8px;"
                f"}}"
            )

        # Tab buttons
        for btn, _ in self._tab_buttons:
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {tm.color('surface_alt')};"
                f"  color: {tm.color('text_secondary')};"
                f"  border: 1px solid {tm.color('border')};"
                f"  border-radius: 16px;"
                f"  padding: 6px 14px;"
                f"  font-size: 12px;"
                f"  font-weight: 600;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background-color: {tm.color('btn_secondary_hover')};"
                f"}}"
                f"QPushButton:checked {{"
                f"  background-color: {tm.color('primary')};"
                f"  color: {tm.color('text_on_primary')};"
                f"  border-color: {tm.color('primary')};"
                f"}}"
            )


        # Table selection + hover styles.
        # `:hover:!selected` is the key — hover should only apply to
        # non-selected rows, otherwise the selected row loses its
        # highlight the moment the mouse enters it.
        if hasattr(self, "table"):
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

    def _style_footer(self):
        tm = theme()
        self.footer_label.setStyleSheet(
            f"QLabel {{ color: {tm.color('text_secondary')};"
            f" background: transparent; font-size: 11px; }}"
        )

    def restyle(self):
        self._style_summary()
        self._style_footer()
        if hasattr(self, "_rows"):
            self._render_rows(self._rows)

    # ---------- actions ----------

    def _on_add_player(self):
        dialog = PlayerFormDialog(parent=self)
        if dialog.exec():
            self._loaded = False   # force re-fetch on next show
            self._reload_activity_tabs()
            self.refresh()
            qr_path = getattr(dialog, "newly_created_qr_path", None)
            if qr_path:
                name = dialog.name_input.text().strip()
                preview = QRPreviewDialog(name, dialog.saved_player_id, qr_path, parent=self)
                preview.exec()

    def _on_row_double_clicked(self, row: int, column: int):
        if row < 0 or row >= len(self._rows):
            return
        player = self._rows[row]["player"]
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
        self._loaded = False
        self._reload_activity_tabs()
        self.refresh()