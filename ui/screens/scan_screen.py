"""
Receptionist scan screen — v4 with activity selector and live recent panel.

Recent Check-ins card:
  * Auto-refreshes every 5 s while this screen is visible
  * Shows only today's entries
  * Rich rows: status icon, time, name, activity, reason/override
  * Double-click → opens the player's detail screen
  * Right-click → context menu (Open player, Undo check-in)
  * Filter row: result, activity, name search
  * Footer button → jump to the Audit log
"""

from datetime import date
import os
import sys
from ui.formatting import format_attendance_row, is_ar
import logging
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QStackedWidget, QComboBox,
    QMenu,
)
from qtpy.QtCore import Qt, QTimer, QPoint
from qtpy.QtGui import QImage, QPixmap, QColor, QAction

from ui.message_box import warn
from ui.formatting import format_attendance_row

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_academy_name
from repositories import players_repo, attendance_repo
from services import attendance_service, subscription_service, activity_service
from services.checkin_service import perform_check_in
from logic.qr_utils import decode_qr_from_frame
from ui.cards.player_card import PlayerCardWidget
from ui.components import SectionCard, Toolbar, Pill
from ui.theme import theme, make_danger, make_secondary, ThemedWidget
from ui.design import SPACING, RADIUS
from ui.i18n import t


CARD_DISPLAY_MS = 2500
REFRESH_INTERVAL_MS = 5000     # recent check-ins auto-refresh
AUTO_ACTIVITY = -1             # sentinel for "Auto" in the session selector


class ScanScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._cap = None
        self._camera_timer = QTimer(self)
        self._camera_timer.timeout.connect(self._poll_camera)
        self._awaiting_clear = False

        # Auto-refresh timer for the recent panel
        self._recent_timer = QTimer(self)
        self._recent_timer.timeout.connect(self._refresh_recent_checkins)
        self._recent_timer.setInterval(REFRESH_INTERVAL_MS)

        self._recent_rows = []       # cached rows for context-menu lookups
        self._loaded = False
        self._camera_fail_count = 0   # consecutive read failures

        self._build_ui()
        # NOTE: don't call _refresh_recent_checkins() here. It runs on
        # first show instead (see showEvent) to speed up MainWindow
        # construction — this screen is eagerly built even when the
        # user never opens it.
        self._init_theme()

    # ---------- show/hide handling for the refresh timer ----------

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self._refresh_recent_checkins()
        self._recent_timer.start()

    def hideEvent(self, event):
        self._recent_timer.stop()
        super().hideEvent(event)

    # ---------- construction ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        # Toolbar: session selector + camera controls
        self.toolbar = Toolbar()

        self.session_label = QLabel(t("checkin.session.label"))
        self.session_input = QComboBox()
        self.session_input.setMinimumWidth(200)
        self._reload_activities()
        self.session_input.currentIndexChanged.connect(self._on_session_changed)

        self.camera_status_pill = Pill(t("checkin.status.camera_off"), "neutral")
        self.start_scan_button = QPushButton(t("checkin.btn.start_scan"))
        self.stop_scan_button = QPushButton(t("checkin.btn.stop_scan"))
        make_danger(self.stop_scan_button)
        self.stop_scan_button.setEnabled(False)

        self.start_scan_button.clicked.connect(self._on_start_scan_clicked)
        self.stop_scan_button.clicked.connect(self._on_stop_scan_clicked)

        self.toolbar.add_leading(self.session_label)
        self.toolbar.add_leading(self.session_input, stretch=1)
        self.toolbar.add_trailing(self.camera_status_pill)
        self.toolbar.add_trailing(self.start_scan_button)
        self.toolbar.add_trailing(self.stop_scan_button)

        root.addWidget(self.toolbar)

        # Main row: camera card + recent card
        main_row = QHBoxLayout()
        main_row.setSpacing(SPACING["lg"])

        # Camera card
        self.camera_card = SectionCard(title=t("checkin.card.camera"))
        self.stack = QStackedWidget()
        self.camera_card.body.addWidget(self.stack)

        idle = QWidget()
        idle_layout = QVBoxLayout(idle)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        idle_layout.setSpacing(SPACING["sm"])

        self.camera_label = QLabel(t("checkin.camera_off"))
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setMinimumHeight(320)
        idle_layout.addWidget(self.camera_label, stretch=1)

        self.camera_hint = QLabel(t("checkin.camera_hint"))
        self.camera_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idle_layout.addWidget(self.camera_hint)

        self.stack.addWidget(idle)

        result = QWidget()
        result_layout = QVBoxLayout(result)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.addStretch()
        self.player_card = PlayerCardWidget()
        result_layout.addWidget(self.player_card)
        result_layout.addStretch()
        self.stack.addWidget(result)

        self.stack.setCurrentIndex(0)
        main_row.addWidget(self.camera_card, stretch=3)

        # --- Recent check-ins card ---
        self.recent_card = SectionCard(title=t("checkin.recent.title"))

        # Filter row
        filters = QHBoxLayout()
        filters.setSpacing(SPACING["sm"])

        self.result_filter = QComboBox()
        self.result_filter.addItem(t("checkin.recent.filter.all"), None)
        self.result_filter.addItem(t("checkin.recent.filter.allowed"), "allowed")
        self.result_filter.addItem(t("checkin.recent.filter.denied"), "denied")
        self.result_filter.addItem(t("checkin.recent.filter.override"), "override")
        self.result_filter.currentIndexChanged.connect(self._render_recent)

        self.activity_filter = QComboBox()
        self.activity_filter.addItem(t("checkin.recent.filter.all_activities"), None)
        for act in activity_service.list_active():
            name = act.name
            self.activity_filter.addItem(name, act.activity_id)
        self.activity_filter.currentIndexChanged.connect(self._render_recent)

        self.name_search = QLineEdit()
        self.name_search.setPlaceholderText(t("checkin.recent.search_placeholder"))
        self.name_search.textChanged.connect(self._render_recent)

        filters.addWidget(self.result_filter)
        filters.addWidget(self.activity_filter)
        filters.addWidget(self.name_search, stretch=1)
        self.recent_card.body.addLayout(filters)

        # List
        self.recent_list = QListWidget()
        self.recent_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recent_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.recent_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.recent_list.customContextMenuRequested.connect(
            self._on_recent_context_menu
        )
        self.recent_list.itemDoubleClicked.connect(
            self._on_recent_item_double_clicked
        )
        self.recent_list.setMinimumHeight(280)
        self.recent_card.body.addWidget(self.recent_list)

        # Empty-state label (hidden when there are rows)
        self.recent_empty = QLabel(t("checkin.recent.empty"))
        self.recent_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recent_empty.setWordWrap(True)
        self.recent_empty.hide()
        self.recent_card.body.addWidget(self.recent_empty)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(SPACING["sm"])

        self.auto_refresh_hint = QLabel(t("checkin.recent.auto_refresh"))
        self.auto_refresh_hint.setStyleSheet("font-size: 11px;")
        footer.addWidget(self.auto_refresh_hint)
        footer.addStretch()

        self.open_full_button = QPushButton(t("checkin.recent.open_full"))
        make_secondary(self.open_full_button)
        self.open_full_button.clicked.connect(self._on_open_full_log)
        footer.addWidget(self.open_full_button)

        self.recent_card.body.addLayout(footer)

        main_row.addWidget(self.recent_card, stretch=2)
        root.addLayout(main_row, stretch=1)

        # Manual check-in card
        self.search_card = SectionCard(title=t("checkin.card.manual"))
        search_row = QHBoxLayout()
        search_row.setSpacing(SPACING["sm"])

        self.manual_search_input = QLineEdit()
        self.manual_search_input.setPlaceholderText(
            t("checkin.search.placeholder")
        )
        self.manual_search_input.setProperty("cssClass", "search")
        self.manual_search_input.returnPressed.connect(self._on_manual_search)

        self.manual_search_button = QPushButton(t("checkin.search.button"))
        self.manual_search_button.clicked.connect(self._on_manual_search)
                # Add this right after the search input/button layout
        self.search_error_label = QLabel(t("checkin.search.required"))
        self.search_error_label.setStyleSheet("color: #e74c3c; font-size: 12px; margin-top: 4px;")
        self.search_error_label.hide()
        # Assuming your layout variable is `layout` or `root`:
        root.addWidget(self.search_error_label) 

        search_row.addWidget(self.manual_search_input, stretch=1)
        search_row.addWidget(self.manual_search_button)
        self.search_card.body.addLayout(search_row)

        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(160)
        self.results_list.hide()
        self.results_list.itemClicked.connect(self._on_manual_result_selected)
        self.search_card.body.addWidget(self.results_list)

        root.addWidget(self.search_card)

    def _reload_activities(self):
        self.session_input.blockSignals(True)
        self.session_input.clear()
        self.session_input.addItem(t("checkin.session.auto"), AUTO_ACTIVITY)
        for act in activity_service.list_active():
            display = act.name
            self.session_input.addItem(display, act.activity_id)
        self.session_input.setCurrentIndex(0)
        self.session_input.blockSignals(False)

    def _current_activity_id(self):
        val = self.session_input.currentData()
        if val is None or val == AUTO_ACTIVITY:
            return None
        return val

    def _on_session_changed(self, _index):
        pass

    # ---------- theming ----------

    def restyle(self):
        tm = theme()

        self.session_label.setStyleSheet(
            f"QLabel {{ color: {tm.color('text_secondary')};"
            f" background-color: transparent; font-size: 13px;"
            f" font-weight: 600; padding-right: 6px; }}"
        )
        self.camera_hint.setStyleSheet(
            f"QLabel {{ color: {tm.color('text_secondary')};"
            f" background-color: transparent; font-size: 12px; }}"
        )
        self.camera_label.setStyleSheet(
            f"QLabel {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"  color: {tm.color('text_secondary')};"
            f"  font-size: 15px;"
            f"  border-radius: {RADIUS['md']}px;"
            f"  border: 1px dashed {tm.color('border')};"
            f"}}"
        )
        self.recent_empty.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-style: italic;"
            f"  padding: 24px;"
            f"  font-size: 13px;"
            f"}}"
        )
        self.auto_refresh_hint.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 11px;"
            f"}}"
        )
        self.recent_list.setStyleSheet(
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
            f"QListWidget::item:selected {{"
            f"  background-color: {tm.color('primary_soft')};"
            f"}}"
        )
        self.results_list.setStyleSheet(
            f"QListWidget {{"
            f"  background-color: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {tm.color('border')} 0;"
            f"  padding: 4px;"
            f"  outline: none;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 8px 10px;"
            f"  border-radius: {RADIUS['xs']}px;"
            f"  color: {tm.color('text')};"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background-color: {tm.color('primary_soft')};"
            f"}}"
        )

    # ---------- camera ----------

    def _on_start_scan_clicked(self):
        self.start_camera()

    def _on_stop_scan_clicked(self):
        self.stop_camera()
        self.camera_label.setText(t("checkin.camera_off"))
        self.camera_status_pill.set_status(t("checkin.status.camera_off"), "neutral")
        self.start_scan_button.setEnabled(True)
        self.stop_scan_button.setEnabled(False)

    def start_camera(self, camera_index: int = 0):
        import cv2
        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            self.camera_label.setText(t("checkin.camera_unavailable"))
            self.camera_status_pill.set_status(t("checkin.status.unavailable"), "error")
            self._cap = None
            return
        self._camera_fail_count = 0
        self._camera_timer.start(200)
        self.camera_status_pill.set_status(t("checkin.status.scanning"), "success")
        self.start_scan_button.setEnabled(False)
        self.stop_scan_button.setEnabled(True)

    def stop_camera(self):
        self._camera_timer.stop()
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _poll_camera(self):
        if self._cap is None or self._awaiting_clear:
            return
        ret, frame = self._cap.read()
        if not ret:
            # Camera may have been unplugged. Count consecutive failures;
            # after 5 (about 1 second at 200ms interval), stop the timer
            # and surface the state so the receptionist can act.
            self._camera_fail_count += 1
            if self._camera_fail_count >= 5:
                self._handle_camera_lost()
            return
        # Successful read — reset the counter.
        self._camera_fail_count = 0
        self._render_frame(frame)
        player_id_str = decode_qr_from_frame(frame)
        if player_id_str:
            try:
                player_id = int(player_id_str)
            except ValueError:
                return
            self.handle_player_id(player_id)
    def _handle_camera_lost(self):
        """Camera stopped returning frames. Stop the loop and notify."""
        logging.getLogger(__name__).warning(
            "Camera stopped responding — stopping scan loop"
        )
        self.stop_camera()
        self.camera_label.setText(t("checkin.camera_unavailable"))
        self.camera_status_pill.set_status(
            t("checkin.status.unavailable"), "error"
        )
        self.start_scan_button.setEnabled(True)
        self.stop_scan_button.setEnabled(False)
    def _render_frame(self, frame):
        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qt_image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        self.camera_label.setPixmap(
            QPixmap.fromImage(qt_image).scaled(
                self.camera_label.width(), self.camera_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
            )
        )

    # ---------- recent check-ins (rich, auto-refresh, filters) ----------

    def _refresh_recent_checkins(self):
        try:
            rows = attendance_repo.get_today_with_details(limit=100)
        except Exception:
            logging.getLogger(__name__).exception("Recent query failed")
            rows = []
        self._recent_rows = rows
        self._render_recent()

    def _render_recent(self):
        # Pull the current filter values
        result_filter = self.result_filter.currentData()
        activity_filter = self.activity_filter.currentData()
        name_query = self.name_search.text().strip().lower()

        filtered = []
        for r in self._recent_rows:
            # Result filter
            if result_filter == "allowed":
                if r["result"] != "allowed" or r["was_override"]:
                    continue
            elif result_filter == "denied":
                if r["result"] != "denied":
                    continue
            elif result_filter == "override":
                if not r["was_override"]:
                    continue

            # Activity filter
            if activity_filter is not None and r["activity_id"] != activity_filter:
                continue

            # Name search
            if name_query and name_query not in (r["player_name"] or "").lower():
                continue

            filtered.append(r)

        self.recent_list.clear()
        tm = theme()

        if not filtered:
            self.recent_list.hide()
            self.recent_empty.show()
            return

        self.recent_list.show()
        self.recent_empty.hide()

        for r in filtered:
            text = format_attendance_row(r)
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, r)
            # Color: denied = danger, override = warning, else text
            if r["result"] == "denied":
                item.setForeground(QColor(tm.color("danger")))
            elif r["was_override"]:
                item.setForeground(QColor(tm.color("warning")))
            else:
                item.setForeground(QColor(tm.color("text")))
            self.recent_list.addItem(item)


    # ---------- context menu ----------

    def _on_recent_context_menu(self, pos: QPoint):
        item = self.recent_list.itemAt(pos)
        if item is None:
            return
        row = item.data(Qt.ItemDataRole.UserRole)
        if not row:
            return

        menu = QMenu(self)

        open_action = QAction(t("checkin.recent.menu.open"), self)
        open_action.triggered.connect(lambda: self._open_player(row["player_id"]))
        menu.addAction(open_action)

        # Undo — only for allowed entries that haven't been overridden and
        # are from today
        can_undo = (
            row["result"] == "allowed"
            and row.get("subscription_id") is not None
        )
        undo_action = QAction(t("checkin.recent.menu.undo"), self)
        undo_action.setEnabled(can_undo)
        undo_action.triggered.connect(lambda: self._undo_recent(row))
        menu.addAction(undo_action)

        menu.exec(self.recent_list.mapToGlobal(pos))

    def _undo_recent(self, row: dict):
        log_id = row.get("log_id")
        if log_id is None:
            return
        # Confirm before undoing
        ok = warn if False else None
        # Actually we want an ask()-style confirm. Import here to avoid
        # circulars at module load.
        from ui.message_box import ask
        if not ask(
            self,
            t("checkin.recent.confirm_undo_title"),
            t("checkin.recent.confirm_undo_msg", name=row.get("player_name") or ""),
        ):
            return
        try:
            from services import attendance_service
            success = attendance_service.undo_check_in(log_id, date.today())
        except Exception:
            success = False

        if success:
            # Audit
            try:
                from services import audit_service
                audit_service.attendance_undone(
                    log_id=log_id, player_id=row["player_id"]
                )
            except Exception:
                pass
            self._refresh_recent_checkins()
        else:
            warn(
                self,
                t("checkin.recent.undo_failed_title"),
                t("checkin.recent.undo_failed_msg"),
            )

    # ---------- recent click handlers ----------

    def _on_recent_item_double_clicked(self, item: QListWidgetItem):
        row = item.data(Qt.ItemDataRole.UserRole)
        if not row:
            return
        self._open_player(row["player_id"])

    def _open_player(self, player_id: int):
        """Route to Manage Players → open this player's detail."""
        try:
            from qtpy.QtWidgets import QApplication
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
        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to open player %s", player_id
            )

    def _on_open_full_log(self):
        """Open the full attendance-log dialog (works for all roles)."""
        from ui.dialogs.today_log_dialog import TodayLogDialog
        dlg = TodayLogDialog(parent=self)
        dlg.exec()
        # In case the user undid something from inside the dialog,
        # keep the inline Recent panel in sync.
        self._refresh_recent_checkins()

    # ---------- manual search (unchanged behavior) ----------

    def _on_manual_search(self):
        query = self.manual_search_input.text().strip()
        
        # --- NEW: Show warning if empty ---
        if not query:
            self.search_error_label.show()
            self.results_list.hide() # Hide previous results
            return
        else:
            self.search_error_label.hide()
        # ----------------------------------

        self.results_list.clear()
        results = []
        if query.isdigit():
            by_id = players_repo.get_by_id(int(query))
            if by_id:
                results.append(by_id)
        if not results:
            results.extend(players_repo.search_by_name(query))

        if not results:
            item = QListWidgetItem(t("checkin.search.no_match"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setForeground(QColor(theme().color("text_secondary")))
            self.results_list.addItem(item)
            self.results_list.show()
            return

        tm = theme()
        for player in results:
            it = QListWidgetItem(f"{player.full_name}   —   ID {player.player_id}")
            it.setData(Qt.ItemDataRole.UserRole, player.player_id)
            it.setForeground(QColor(tm.color("text")))
            self.results_list.addItem(it)
        self.results_list.show()

    def _on_manual_result_selected(self, item: QListWidgetItem):
        player_id = item.data(Qt.ItemDataRole.UserRole)
        if player_id is None:
            return
        self.results_list.hide()
        self.manual_search_input.clear()
        self.handle_player_id(player_id)

    # ---------- pipeline ----------

    def handle_player_id(self, player_id: int, recorded_by: str = None):
        activity_id = self._current_activity_id()
        outcome = perform_check_in(
            player_id,
            parent_widget=self,
            recorded_by=recorded_by,
            preselect_activity_id=activity_id,
        )
        if outcome is None:
            warn(
                self,
                t("checkin.unknown_player_title"),
                t("checkin.unknown_player_msg", player_id=player_id),
            )
            return

        if getattr(outcome, "was_duplicate", False):
            warn(
                self,
                t("checkin.already_today_title"),
                t("checkin.already_today_msg", name=outcome.player.full_name),
            )
            return

        if getattr(outcome, "not_enrolled_in_activity", False):
            warn(
                self,
                t("checkin.not_enrolled.title"),
                t("checkin.not_enrolled.msg",
                  name=outcome.player.full_name,
                  activity=outcome.missing_activity_name),
            )
            return

        if getattr(outcome, "needs_picker", False):
            from ui.dialogs.activity_picker_dialog import ActivityPickerDialog
            picker = ActivityPickerDialog(
                outcome.player.full_name,
                outcome.valid_subscriptions,
                parent=self,
            )
            if picker.exec() != picker.DialogCode.Accepted:
                return
            outcome = perform_check_in(
                player_id,
                parent_widget=self,
                recorded_by=recorded_by,
                preselect_subscription_id=picker.chosen_subscription_id,
            )
            if outcome is None:
                return

        state = "checked_in" if outcome.checked_in else "denied"
        self.player_card.display_player(outcome.player, outcome.subscription, check_in_state=state)
        self.stack.setCurrentIndex(1)
        self._refresh_recent_checkins()
        self._schedule_return_to_idle()

    def _schedule_return_to_idle(self):
        self._awaiting_clear = True
        QTimer.singleShot(CARD_DISPLAY_MS, self._return_to_idle)

    def _return_to_idle(self):
        self.player_card.clear()
        self.stack.setCurrentIndex(0)
        self._awaiting_clear = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

