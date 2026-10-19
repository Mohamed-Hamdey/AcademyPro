"""
Full attendance log dialog — opened from the scan screen's
"فتح السجل الكامل" button.

Works for every role: it reads attendance_log directly, no audit
permission required.

Features:
  * Date picker + step arrows + Today button (matches dashboard pattern)
  * Filter row: result / activity / name search
  * Rich rows, same format as the scan screen's Recent panel
  * Double-click a row → opens the player's detail screen
  * Right-click a row → Open player / Undo check-in
  * Auto-refreshes if the selected date is today (so it stays in sync
    with live check-ins happening behind the dialog)
"""

from datetime import date
import logging
from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QComboBox, QDateEdit, QMenu, QApplication,
)
from qtpy.QtCore import Qt, QDate, QTimer, QPoint
from qtpy.QtGui import QColor, QAction

from repositories import attendance_repo
from services import activity_service, attendance_service
from ui.components import EmptyState
from ui.theme import theme, make_secondary, ThemedWidget
from ui.design import SPACING
from ui.i18n import t
from ui.formatting import format_attendance_row, is_ar
from ui.message_box import warn, ask


REFRESH_INTERVAL_MS = 5000  # only ticks while the picked date is today


class TodayLogDialog(ThemedWidget, QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(t("checkin.full_log.title"))
        self.setModal(True)
        self.setMinimumSize(900, 600)
        self.resize(900, 600)

        self._rows = []

        # Auto-refresh only matters if we're looking at today.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._reload)
        self._refresh_timer.setInterval(REFRESH_INTERVAL_MS)

        self._build_ui()
        self._reload()
        self._init_theme()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        # ---- Top row: date picker + step arrows + Today ----
        top = QHBoxLayout()
        top.setSpacing(SPACING["sm"])

        self.date_label = QLabel(t("checkin.full_log.date_label"))
        top.addWidget(self.date_label)

        self.prev_day_button = QPushButton("◀")
        self.prev_day_button.setFixedWidth(36)
        make_secondary(self.prev_day_button)
        self.prev_day_button.clicked.connect(lambda: self._shift_day(-1))
        top.addWidget(self.prev_day_button)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)
        top.addWidget(self.date_edit)

        self.next_day_button = QPushButton("▶")
        self.next_day_button.setFixedWidth(36)
        make_secondary(self.next_day_button)
        self.next_day_button.clicked.connect(lambda: self._shift_day(1))
        top.addWidget(self.next_day_button)

        self.today_button = QPushButton(t("checkin.full_log.btn_today"))
        make_secondary(self.today_button)
        self.today_button.clicked.connect(self._jump_to_today)
        top.addWidget(self.today_button)

        top.addStretch()

        self.count_label = QLabel("")
        top.addWidget(self.count_label)

        root.addLayout(top)

        # ---- Filter row ----
        filters = QHBoxLayout()
        filters.setSpacing(SPACING["sm"])

        self.result_filter = QComboBox()
        self.result_filter.addItem(t("checkin.recent.filter.all"), None)
        self.result_filter.addItem(t("checkin.recent.filter.allowed"), "allowed")
        self.result_filter.addItem(t("checkin.recent.filter.denied"), "denied")
        self.result_filter.addItem(t("checkin.recent.filter.override"), "override")
        self.result_filter.currentIndexChanged.connect(self._render)
        filters.addWidget(self.result_filter)

        self.activity_filter = QComboBox()
        self.activity_filter.addItem(t("checkin.recent.filter.all_activities"), None)
        for act in activity_service.list_active():
            name = act.name_ar if is_ar() else act.name_en
            self.activity_filter.addItem(name, act.activity_id)
        self.activity_filter.currentIndexChanged.connect(self._render)
        filters.addWidget(self.activity_filter)

        self.name_search = QLineEdit()
        self.name_search.setPlaceholderText(t("checkin.recent.search_placeholder"))
        self.name_search.textChanged.connect(self._render)
        filters.addWidget(self.name_search, stretch=1)

        root.addLayout(filters)

        # ---- List ----
        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setFrameShape(QListWidget.Shape.NoFrame)
        self.list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        root.addWidget(self.list_widget, stretch=1)

        # ---- Empty state (shown instead of the list when there are no rows) ----
        self.empty_state = EmptyState(
            icon="📭",
            message=t("checkin.full_log.empty"),
        )
        root.addWidget(self.empty_state, stretch=1)
        self.empty_state.hide()

        # ---- Footer ----
        footer = QHBoxLayout()
        footer.addStretch()
        self.close_button = QPushButton(t("checkin.full_log.btn_close"))
        make_secondary(self.close_button)
        self.close_button.clicked.connect(self.accept)
        footer.addWidget(self.close_button)
        root.addLayout(footer)

    # ------------------------------------------------------------------
    # Date navigation
    # ------------------------------------------------------------------

    def _selected_date(self) -> date:
        qd = self.date_edit.date()
        return date(qd.year(), qd.month(), qd.day())

    def _shift_day(self, delta: int):
        self.date_edit.setDate(self.date_edit.date().addDays(delta))

    def _jump_to_today(self):
        self.date_edit.setDate(QDate.currentDate())

    def _on_date_changed(self, _qd):
        # Start/stop the auto-refresh depending on whether we're on today.
        if self._selected_date() == date.today():
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()
        self._reload()

    def showEvent(self, event):
        super().showEvent(event)
        if self._selected_date() == date.today():
            self._refresh_timer.start()

    def hideEvent(self, event):
        self._refresh_timer.stop()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # Data load + render
    # ------------------------------------------------------------------

    def _reload(self):
        try:
            day = self._selected_date()
            if day == date.today():
                rows = attendance_repo.get_today_with_details(limit=500)
            else:
                rows = attendance_repo.get_by_date_with_details(day, limit=500)
        except Exception:
            logging.getLogger(__name__).exception("Query failed")
            rows = []
        self._rows = rows
        self._render()

    def _render(self):
        result_filter = self.result_filter.currentData()
        activity_filter = self.activity_filter.currentData()
        name_query = self.name_search.text().strip().lower()

        filtered = []
        for r in self._rows:
            if result_filter == "allowed":
                if r["result"] != "allowed" or r["was_override"]:
                    continue
            elif result_filter == "denied":
                if r["result"] != "denied":
                    continue
            elif result_filter == "override":
                if not r["was_override"]:
                    continue

            if activity_filter is not None and r["activity_id"] != activity_filter:
                continue

            if name_query and name_query not in (r["player_name"] or "").lower():
                continue

            filtered.append(r)

        self.list_widget.clear()
        self.count_label.setText(
            t("checkin.full_log.count", n=len(filtered))
        )

        if not filtered:
            self.list_widget.hide()
            self.empty_state.show()
            return

        self.list_widget.show()
        self.empty_state.hide()

        tm = theme()
        for r in filtered:
            item = QListWidgetItem(format_attendance_row(r))
            item.setData(Qt.ItemDataRole.UserRole, r)
            if r["result"] == "denied":
                item.setForeground(QColor(tm.color("danger")))
            elif r["was_override"]:
                item.setForeground(QColor(tm.color("warning")))
            else:
                item.setForeground(QColor(tm.color("text")))
            self.list_widget.addItem(item)

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

    def restyle(self):
        tm = theme()
        self.date_label.setStyleSheet(
            f"QLabel {{ color: {tm.color('text_secondary')};"
            f" background-color: transparent; font-size: 13px;"
            f" font-weight: 600; padding-right: 6px; }}"
        )
        self.count_label.setStyleSheet(
            f"QLabel {{ color: {tm.color('text_secondary')};"
            f" background-color: transparent; font-size: 12px; }}"
        )
        self.list_widget.setStyleSheet(
            f"QListWidget {{"
            f"  background-color: transparent;"
            f"  border: none;"
            f"  padding: 0;"
            f"  outline: none;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 8px 10px;"
            f"  border-radius: 4px;"
            f"  color: {tm.color('text')};"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background-color: {tm.color('primary_soft')};"
            f"}}"
        )

    # ------------------------------------------------------------------
    # Row actions
    # ------------------------------------------------------------------

    def _on_item_double_clicked(self, item: QListWidgetItem):
        row = item.data(Qt.ItemDataRole.UserRole)
        if row:
            self._open_player(row["player_id"])

    def _on_context_menu(self, pos: QPoint):
        item = self.list_widget.itemAt(pos)
        if item is None:
            return
        row = item.data(Qt.ItemDataRole.UserRole)
        if not row:
            return

        menu = QMenu(self)

        open_action = QAction(t("checkin.recent.menu.open"), self)
        open_action.triggered.connect(lambda: self._open_player(row["player_id"]))
        menu.addAction(open_action)

        can_undo = (
            row["result"] == "allowed"
            and row.get("subscription_id") is not None
        )
        undo_action = QAction(t("checkin.recent.menu.undo"), self)
        undo_action.setEnabled(can_undo)
        undo_action.triggered.connect(lambda: self._undo(row))
        menu.addAction(undo_action)

        menu.exec(self.list_widget.mapToGlobal(pos))

    def _undo(self, row: dict):
        log_id = row.get("log_id")
        if log_id is None:
            return
        if not ask(
            self,
            t("checkin.recent.confirm_undo_title"),
            t("checkin.recent.confirm_undo_msg", name=row.get("player_name") or ""),
        ):
            return
        try:
            success = attendance_service.undo_check_in(log_id, date.today())
        except Exception:
            success = False

        if success:
            try:
                from services import audit_service
                audit_service.attendance_undone(
                    log_id=log_id, player_id=row["player_id"]
                )
            except Exception:
                pass
            self._reload()
        else:
            warn(
                self,
                t("checkin.recent.undo_failed_title"),
                t("checkin.recent.undo_failed_msg"),
            )

    def _open_player(self, player_id: int):
        """Route to Manage Players → open this player's detail."""
        app = QApplication.instance()
        if app is None:
            return
        w = self
        main_win = None
        while w is not None:
            if hasattr(w, "_pages_by_nav_key") and hasattr(w, "sidebar"):
                main_win = w
                break
            w = w.parentWidget() if hasattr(w, "parentWidget") else None
        if main_win is None:
            return
        nav_keys = getattr(main_win, "_nav_keys_in_order", [])
        if "nav.manage_players" in nav_keys:
            idx = nav_keys.index("nav.manage_players")
            main_win.sidebar.set_current_row(idx)
        screen = main_win._pages_by_nav_key.get("nav.manage_players")
        if screen is not None and hasattr(screen, "_open_detail"):
            screen._open_detail(player_id)
        self.accept()  # close the dialog so the player screen is visible