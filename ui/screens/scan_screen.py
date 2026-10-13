"""
Receptionist scan screen — v4 design.

Layout (RTL: controls on the right, content mirrored):
    ┌──────────────────────────────────────────────────────────┐
    │  [Status pill] [▶ Start Scan] [■ Stop Scan]              │  ← Toolbar
    │                                                          │
    │  ┌─ Camera (SectionCard) ─────┐  ┌─ Recent (SectionCard)─┐│
    │  │   [camera preview]         │  │  ✓ 09:12  أحمد       ││
    │  │   hint                     │  │  ✕ 09:10  محمود       ││
    │  └────────────────────────────┘  └───────────────────────┘│
    │                                                          │
    │  ┌─ Manual check-in (SectionCard) ───────────────────────┐│
    │  │  [search input]                    [Search button]    ││
    │  │  [results list — appears on demand]                   ││
    │  └───────────────────────────────────────────────────────┘│
    └──────────────────────────────────────────────────────────┘

The screen no longer carries its own page title; the workspace header
shows it (see ui/main_window.py + ui/shell.py).
"""

import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QColor

from ui.message_box import warn

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_academy_name
from repositories import players_repo
from services import attendance_service
from services.checkin_service import perform_check_in
from logic.qr_utils import decode_qr_from_frame
from ui.cards.player_card import PlayerCardWidget
from ui.components import SectionCard, Toolbar, EmptyState, Pill
from ui.theme import theme, make_danger, make_secondary, ThemedWidget
from ui.design import SPACING, RADIUS
from ui.i18n import t


CARD_DISPLAY_MS = 2500


class ScanScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._cap = None
        self._camera_timer = QTimer(self)
        self._camera_timer.timeout.connect(self._poll_camera)
        self._awaiting_clear = False
        self._build_ui()
        self._refresh_recent_checkins()
        self._init_theme()

    # ---------- construction ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        # ---- Toolbar row: status pill + camera controls ----
        self.toolbar = Toolbar()
        root.addWidget(self.toolbar)

        self.camera_status_pill = Pill(t("checkin.status.camera_off"), "neutral")
        self.start_scan_button = QPushButton(t("checkin.btn.start_scan"))
        self.stop_scan_button = QPushButton(t("checkin.btn.stop_scan"))
        make_danger(self.stop_scan_button)
        self.stop_scan_button.setEnabled(False)

        self.start_scan_button.clicked.connect(self._on_start_scan_clicked)
        self.stop_scan_button.clicked.connect(self._on_stop_scan_clicked)

        self.toolbar.add_leading(self.camera_status_pill)
        self.toolbar.add_trailing(self.start_scan_button)
        self.toolbar.add_trailing(self.stop_scan_button)

        # ---- Main row: camera card + recent card ----
        main_row = QHBoxLayout()
        main_row.setSpacing(SPACING["lg"])

        # Camera card
        self.camera_card = SectionCard(title=t("checkin.card.camera"))
        self.stack = QStackedWidget()
        self.camera_card.body.addWidget(self.stack)

        # Idle page
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

        # Result page (player card)
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

        # Recent check-ins card
        self.recent_card = SectionCard(title=t("checkin.card.recent"))
        self.recent_list = QListWidget()
        self.recent_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recent_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.recent_card.body.addWidget(self.recent_list)
        main_row.addWidget(self.recent_card, stretch=2)

        root.addLayout(main_row, stretch=1)

        # ---- Manual check-in card ----
        self.search_card = SectionCard(title=t("checkin.card.manual"))
        search_row = QHBoxLayout()
        search_row.setSpacing(SPACING["sm"])

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("checkin.search.placeholder"))
        self.search_input.setProperty("cssClass", "search")
        self.search_input.returnPressed.connect(self._on_manual_search)

        self.search_button = QPushButton(t("checkin.search.button"))
        self.search_button.clicked.connect(self._on_manual_search)

        search_row.addWidget(self.search_input, stretch=1)
        search_row.addWidget(self.search_button)
        self.search_card.body.addLayout(search_row)

        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(160)
        self.results_list.hide()
        self.results_list.itemClicked.connect(self._on_manual_result_selected)
        self.search_card.body.addWidget(self.results_list)

        root.addWidget(self.search_card)

    # ---------- theming ----------

    def restyle(self):
        tm = theme()

        self.camera_hint.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
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
        self.recent_list.setStyleSheet(
            f"QListWidget {{"
            f"  background-color: transparent;"
            f"  border: none;"
            f"  padding: 0;"
            f"  outline: none;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 10px 12px;"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  color: {tm.color('text')};"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"}}"
        )
        self.results_list.setStyleSheet(
            f"QListWidget {{"
            f"  background-color: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['sm']}px;"
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
            return
        self._render_frame(frame)
        player_id_str = decode_qr_from_frame(frame)
        if player_id_str:
            try:
                player_id = int(player_id_str)
            except ValueError:
                return
            self.handle_player_id(player_id)

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

    # ---------- recent check-ins ----------

    def _refresh_recent_checkins(self):
        self.recent_list.clear()
        entries = attendance_service.get_recent_with_names(limit=10)
        if not entries:
            placeholder = QListWidgetItem(t("checkin.recent.empty"))
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QColor(theme().color("text_secondary")))
            self.recent_list.addItem(placeholder)
            return
        tm = theme()
        for e in entries:
            time_part = e["scan_datetime"].split(" ")[-1][:5]
            if e["result"] == "allowed":
                dot = "✓" if not e["was_override"] else "✓*"
            else:
                dot = "✕"
            text = f"{dot}   {time_part}   {e['full_name']}"
            item = QListWidgetItem(text)
            item.setForeground(QColor(tm.color("text")))
            self.recent_list.addItem(item)

    # ---------- manual search ----------

    def _on_manual_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
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
        self.search_input.clear()
        self.handle_player_id(player_id)

    # ---------- pipeline ----------

    def handle_player_id(self, player_id: int, recorded_by: str = None):
        outcome = perform_check_in(player_id, parent_widget=self, recorded_by=recorded_by)
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