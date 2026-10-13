"""
Player detail / admin screen — v4 design.

Layout:
    ┌────────────────────────────────────────────────────────────┐
    │  [← Back to Players]                                       │
    │                                                            │
    │  ┌─ Overview ─┬─ Attendance ─┬─ Progress ─┐  ← Tabs        │
    │  │                                          │              │
    │  │  ┌─ Player card ──┐  ┌─ Actions ──────┐  │              │
    │  │  │  photo | info  │  │ Edit, QR, …    │  │              │
    │  │  └────────────────┘  └────────────────┘  │              │
    │  │                                          │              │
    │  │  ┌─ Subscription ────────────────────┐   │              │
    │  │  │  Status · plan · sessions · expiry│   │              │
    │  │  │  [Activate][Suspend][Adjust][Pay] │   │              │
    │  │  └───────────────────────────────────┘   │              │
    │  │                                          │              │
    │  │  ┌─ Notes ───────────────────────────┐   │              │
    │  │  │  textarea           [Save Notes]  │   │              │
    │  │  └───────────────────────────────────┘   │              │
    │  └──────────────────────────────────────────┘              │
    └────────────────────────────────────────────────────────────┘
"""

import os
import sys
import shutil
from datetime import date
from services import audit_service
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QTabWidget, QFileDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_plan_label
from repositories import players_repo
from services import subscription_service, attendance_service
from services.checkin_service import perform_check_in
from ui.cards.player_card import PlayerCardWidget
from ui.dialogs.player_form_dialog import PlayerFormDialog
from ui.dialogs.subscription_form_dialog import SubscriptionFormDialog
from ui.dialogs.adjust_sessions_dialog import AdjustSessionsDialog
from ui.dialogs.update_payment_dialog import UpdatePaymentDialog
from logic.qr_utils import generate_qr_for_player
from ui.screens.progress_view import ProgressPanel
from ui.components import SectionCard, Toolbar, Pill
from ui.theme import theme, ThemedWidget, make_danger, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.message_box import info, warn, ask


class PlayerDetailScreen(ThemedWidget, QWidget):
    def __init__(self, player_id: int, on_back=None, parent=None):
        QWidget.__init__(self, parent)
        self.player_id = player_id
        self.on_back = on_back
        self._build_ui()
        self.refresh()
        self._init_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        # ---- Toolbar: back button ----
        self.toolbar = Toolbar()
        back_button = QPushButton(t("detail.back"))
        make_secondary(back_button)
        back_button.clicked.connect(self._on_back_clicked)
        self.toolbar.add_leading(back_button)
        root.addWidget(self.toolbar)

        # ---- Tabs ----
        tabs = QTabWidget()
        root.addWidget(tabs, stretch=1)

        # ===================== Overview tab =====================
        overview = QWidget()
        ov = QVBoxLayout(overview)
        ov.setContentsMargins(0, SPACING["lg"], 0, 0)
        ov.setSpacing(SPACING["lg"])

        # ---- Player card + action buttons ----
        card_row = QHBoxLayout()
        card_row.setSpacing(SPACING["lg"])
        self.player_card = PlayerCardWidget()
        card_row.addWidget(self.player_card, stretch=1)

        card_buttons = QVBoxLayout()
        card_buttons.setSpacing(SPACING["sm"])
        edit_button = QPushButton(t("detail.player.edit"))
        make_secondary(edit_button)
        reissue_qr_button = QPushButton(t("detail.player.reissue_qr"))
        make_secondary(reissue_qr_button)
        export_qr_button = QPushButton(t("detail.player.export_qr"))
        make_secondary(export_qr_button)
        edit_button.clicked.connect(self._on_edit_player)
        reissue_qr_button.clicked.connect(self._on_reissue_qr)
        export_qr_button.clicked.connect(self._on_export_qr)
        card_buttons.addWidget(edit_button)
        card_buttons.addWidget(reissue_qr_button)
        card_buttons.addWidget(export_qr_button)
        card_buttons.addStretch()
        card_row.addLayout(card_buttons)
        ov.addLayout(card_row)

        # ---- Subscription card ----
        self.sub_card = SectionCard(title=t("detail.sub.group"))
        self.sub_status_label = QLabel()
        self.sub_status_label.setWordWrap(True)
        self.sub_card.body.addWidget(self.sub_status_label)

        sub_buttons = QHBoxLayout()
        sub_buttons.setSpacing(SPACING["sm"])
        self.activate_button = QPushButton(t("detail.sub.activate"))
        self.suspend_button = QPushButton(t("detail.sub.suspend"))
        make_danger(self.suspend_button)
        self.adjust_button = QPushButton(t("detail.sub.adjust"))
        make_secondary(self.adjust_button)
        self.record_payment_button = QPushButton(t("detail.sub.record_payment"))
        make_secondary(self.record_payment_button)
        self.activate_button.clicked.connect(self._on_activate_subscription)
        self.suspend_button.clicked.connect(self._on_suspend_subscription)
        self.adjust_button.clicked.connect(self._on_adjust_sessions)
        self.record_payment_button.clicked.connect(self._on_record_payment)
        for b in (self.activate_button, self.suspend_button,
                  self.adjust_button, self.record_payment_button):
            sub_buttons.addWidget(b)
        sub_buttons.addStretch()
        self.sub_card.body.addLayout(sub_buttons)
        ov.addWidget(self.sub_card)

        # ---- Notes card ----
        self.notes_card = SectionCard(title=t("detail.notes.group"))
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(90)
        save_notes_button = QPushButton(t("detail.notes.save"))
        make_secondary(save_notes_button)
        save_notes_button.clicked.connect(self._on_save_notes)

        self.notes_card.body.addWidget(self.notes_input)

        # Save button on the trailing edge (Qt handles RTL mirroring)
        notes_footer = QHBoxLayout()
        notes_footer.addStretch()
        notes_footer.addWidget(save_notes_button)
        self.notes_card.body.addLayout(notes_footer)

        ov.addWidget(self.notes_card)
        ov.addStretch()

        tabs.addTab(overview, t("detail.tab.overview"))

        # ===================== Attendance tab =====================
        attendance = QWidget()
        att = QVBoxLayout(attendance)
        att.setContentsMargins(0, SPACING["lg"], 0, 0)
        att.setSpacing(SPACING["lg"])

        self.att_card = SectionCard(title=t("detail.att.group"))
        self.attendance_table = QTableWidget(0, 5)
        self.attendance_table.setHorizontalHeaderLabels([
            t("detail.att.col.datetime"),
            t("detail.att.col.result"),
            t("detail.att.col.reason"),
            t("detail.att.col.override"),
            t("detail.att.col.recorded_by"),
        ])
        self.attendance_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.attendance_table.verticalHeader().setVisible(False)
        self.attendance_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.attendance_table.setAlternatingRowColors(True)
        self.attendance_table.setShowGrid(False)
        self.attendance_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.att_card.body.addWidget(self.attendance_table)

        att_buttons = QHBoxLayout()
        att_buttons.setSpacing(SPACING["sm"])
        self.undo_button = QPushButton(t("detail.att.undo"))
        make_secondary(self.undo_button)
        self.manual_checkin_button = QPushButton(t("detail.att.manual"))
        self.undo_button.clicked.connect(self._on_undo_selected)
        self.manual_checkin_button.clicked.connect(self._on_manual_check_in)
        att_buttons.addWidget(self.undo_button)
        att_buttons.addWidget(self.manual_checkin_button)
        att_buttons.addStretch()
        self.att_card.body.addLayout(att_buttons)

        att.addWidget(self.att_card)
        tabs.addTab(attendance, t("detail.tab.attendance"))

        # ===================== Progress tab =====================
        self.progress_panel = ProgressPanel(self.player_id)
        tabs.addTab(self.progress_panel, t("detail.tab.progress"))

    # ---------- theme ----------

    def restyle(self):
        if hasattr(self, "current_player"):
            self._render_sub_status()

    # ---------- data ----------

    def refresh(self):
        player = players_repo.get_by_id(self.player_id)
        if player is None:
            return
        self.current_player = player

        display = subscription_service.get_display_status(self.player_id)
        active_sub = subscription_service.get_active(self.player_id) if display["status"] == "active" else None
        self.current_subscription = active_sub
        self._current_display = display

        self.player_card.display_player(player, active_sub, check_in_state=None)
        self._render_sub_status()

        self.suspend_button.setEnabled(display["status"] == "active")
        self.adjust_button.setEnabled(display["status"] == "active")
        self.record_payment_button.setEnabled(display["subscription_id"] is not None)

        self.notes_input.setPlainText(player.notes or "")
        self._load_attendance()
        self.progress_panel.refresh()

    def _render_sub_status(self):
        tm = theme()
        display = getattr(self, "_current_display", None)
        if display is None:
            return

        status_token = {
            "active": "success", "expired": "danger",
            "suspended": "warning", "none": "text_secondary",
        }.get(display["status"], "text_secondary")
        color = tm.color(status_token)

        status_word = {
            "active":    t("players.status.active"),
            "expired":   t("players.status.expired"),
            "suspended": t("players.status.suspended"),
            "none":      t("players.status.none"),
        }.get(display["status"], t("players.status.none"))

        if display["status"] == "none":
            self.sub_status_label.setText(
                f'<span style="color:{color}; font-weight:700;">{status_word}</span>'
                f'<span style="color:{tm.color("text_secondary")};">'
                f'  —  استخدم «تفعيل / تجديد اشتراك» لتسجيل هذا اللاعب.</span>'
            )
        else:
            self.sub_status_label.setText(
                f'<span style="color:{color}; font-weight:700;">{status_word}</span>'
                f'<span style="color:{tm.color("text_secondary")};">'
                f'  ·  {get_plan_label(display["plan_type"])}'
                f'  ·  متبقٍ {display["sessions_remaining"]}/{display["sessions_total"]} حصة'
                f'  ·  ينتهي في {display["expiry_date"]}</span>'
            )

        # Style the label with a slightly larger font and padded appearance
        self.sub_status_label.setStyleSheet(
            f"QLabel {{"
            f"  background-color: transparent;"
            f"  font-size: 14px;"
            f"  padding: 4px 0;"
            f"}}"
        )

    def _load_attendance(self):
        rows = attendance_service.get_for_player(self.player_id)
        self.attendance_table.setRowCount(len(rows))
        self._attendance_rows = rows

        tm = theme()
        for i, entry in enumerate(rows):
            self.attendance_table.setItem(i, 0, QTableWidgetItem(entry.scan_datetime))
            result_text = t("detail.att.result.allowed") if entry.result == "allowed" else t("detail.att.result.denied")
            result_item = QTableWidgetItem(result_text)
            color = tm.color("success") if entry.result == "allowed" else tm.color("danger")
            result_item.setForeground(QColor(color))
            self.attendance_table.setItem(i, 1, result_item)
            self.attendance_table.setItem(i, 2, QTableWidgetItem(entry.deny_reason or ""))
            self.attendance_table.setItem(
                i, 3,
                QTableWidgetItem(t("detail.att.yes") if entry.was_override else "")
            )
            self.attendance_table.setItem(i, 4, QTableWidgetItem(entry.recorded_by or ""))

    # ---------- actions ----------

    def _on_back_clicked(self):
        if self.on_back:
            self.on_back()

    def _on_edit_player(self):
        dialog = PlayerFormDialog(self.current_player, parent=self)
        if dialog.exec():
            self.refresh()

    def _on_activate_subscription(self):
        dialog = SubscriptionFormDialog(self.player_id, parent=self)
        if dialog.exec():
            self.refresh()

    def _on_suspend_subscription(self):
        if not self.current_subscription:
            return
        if ask(self, t("detail.msg.suspend_title"), t("detail.msg.suspend_body")):
            subscription_service.suspend(self.current_subscription.subscription_id)
            audit_service.subscription_suspended(
                subscription_id=self.current_subscription.subscription_id,
            )
            self.refresh()

    def _on_adjust_sessions(self):
        if not self.current_subscription:
            return
        dialog = AdjustSessionsDialog(
            self.current_subscription.subscription_id,
            self.current_subscription.sessions_remaining,
            self.current_subscription.sessions_total,
            parent=self,
        )
        if dialog.exec():
            old = self.current_subscription.sessions_remaining
            new = dialog.new_value()
            subscription_service.adjust_sessions(
                self.current_subscription.subscription_id, new
            )
            audit_service.subscription_sessions_adjusted(
                subscription_id=self.current_subscription.subscription_id,
                old_value=old,
                new_value=new,
            )
            self.refresh()

    def _on_record_payment(self):
        display = getattr(self, "_current_display", None)
        if not display or display["subscription_id"] is None:
            info(self, t("detail.msg.no_sub_title"), t("detail.msg.no_sub_msg"))
            return
        current_amount = self.current_subscription.payment_amount if self.current_subscription else 0.0
        dialog = UpdatePaymentDialog(current_amount or 0.0, parent=self)
        if dialog.exec():
            amount, payment_date = dialog.get_values()
            subscription_service.record_payment(display["subscription_id"], amount, payment_date)
            audit_service.payment_recorded(
                subscription_id=display["subscription_id"],
                amount=amount,
                payment_date=payment_date.isoformat(),
            )
            self.refresh()

    def _on_export_qr(self):
        if not self.current_player.qr_code_path or not os.path.exists(self.current_player.qr_code_path):
            info(self, t("detail.msg.no_qr_title"), t("detail.msg.no_qr_msg"))
            return
        default_name = f"{self.current_player.full_name.replace(' ', '_')}_QR.png"
        dest_path, _ = QFileDialog.getSaveFileName(
            self, t("detail.msg.export_title"), default_name, "PNG Images (*.png)"
        )
        if dest_path:
            shutil.copy(self.current_player.qr_code_path, dest_path)
            info(self, t("detail.msg.export_done_title"),
                 t("detail.msg.export_done_msg", path=dest_path))

    def _on_undo_selected(self):
        selected = self.attendance_table.selectionModel().selectedRows()
        if not selected:
            info(self, t("detail.att.no_selection"), t("detail.att.no_selection_msg"))
            return
        row_index = selected[0].row()
        entry = self._attendance_rows[row_index]
        if not attendance_service.can_undo(entry, date.today()):
            warn(self, t("detail.att.cannot_undo_title"), t("detail.att.cannot_undo_msg"))
            return
        if attendance_service.undo_check_in(entry.log_id, date.today()):
            audit_service.attendance_undone(
                log_id=entry.log_id,
                player_id=self.player_id,
            )
            self.refresh()
        else:
            warn(self, t("detail.att.undo_failed_title"), t("detail.att.undo_failed_msg"))

    def _on_manual_check_in(self):
        outcome = perform_check_in(self.player_id, parent_widget=self)
        audit_service.manual_checkin(player_id=self.player_id)
        if outcome is None:
            warn(self, t("checkin.unknown_player_title"),
                 t("detail.msg.player_not_found"))
            return
        self.refresh()

    def _on_reissue_qr(self):
        if not ask(self, t("detail.msg.reissue_qr_title"), t("detail.msg.reissue_qr_body")):
            return
        path = generate_qr_for_player(self.player_id)
        self.current_player.qr_code_path = path
        players_repo.update(self.current_player)
        audit_service.qr_reissued(
            player_id=self.player_id,
            name=self.current_player.full_name,
        )
        info(self, t("detail.msg.reissue_qr_done_title"),
             t("detail.msg.reissue_qr_done_msg", path=path))
        self.refresh()

    def _on_save_notes(self):
        self.current_player.notes = self.notes_input.toPlainText().strip() or None
        players_repo.update(self.current_player)