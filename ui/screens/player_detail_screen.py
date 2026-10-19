"""
Player detail / admin screen — v4 with multi-subscription support.

Every tab is wrapped in a scroll area so all sections remain reachable
even when the window is short or there are many rows.
"""

import os
import sys
import shutil
from datetime import date
from ui.screens.player_records_tab import PlayerRecordsTab
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidgetItem, QTextEdit, QTabWidget, QFileDialog,
    QScrollArea, QFrame,
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from ui.table_helpers import make_standard_table
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_plan_label
from repositories import players_repo, subscriptions_repo
from services import subscription_service, attendance_service, activity_service, audit_service
from services.checkin_service import perform_check_in
from ui.cards.player_card import PlayerCardWidget
from ui.dialogs.player_form_dialog import PlayerFormDialog
from ui.dialogs.subscription_form_dialog import SubscriptionFormDialog
from ui.dialogs.update_payment_dialog import UpdatePaymentDialog
from logic.qr_utils import generate_qr_for_player
from ui.components import SectionCard
from ui.theme import theme, ThemedWidget, make_danger, make_secondary, make_warning
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.dialogs.edit_subscription_dialog import EditSubscriptionDialog
from ui.message_box import info, warn, ask


class PlayerDetailScreen(ThemedWidget, QWidget):
    def __init__(self, player_id: int, on_back=None, parent=None):
        QWidget.__init__(self, parent)
        self.player_id = player_id
        self.on_back = on_back
        self._active_subs = []
        self._build_ui()
        self.refresh()
        self._init_theme()

    # ---------- UI ----------
    # ---------- lifecycle: header action hook ----------

    def showEvent(self, event):
        super().showEvent(event)
        self._install_header_action()

    def hideEvent(self, event):
        self._uninstall_header_action()
        super().hideEvent(event)

    def _install_header_action(self):
        """Ask the enclosing Workspace to show our Back button."""
        try:
            self.back_button.objectName()
        except RuntimeError:
            self.back_button = QPushButton(t("detail.back"))
            self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.back_button.clicked.connect(self._on_back_clicked)

        ws = self._find_workspace()
        if ws is not None and hasattr(ws, "set_header_action"):
            ws.set_header_action(self.back_button)

    def _uninstall_header_action(self):
        """Remove the Back button from the Workspace header."""
        ws = self._find_workspace()
        if ws is not None and hasattr(ws, "set_header_action"):
            if getattr(ws, "_header_action_widget", None) is self.back_button:
                ws.set_header_action(None)

    def _find_workspace(self):
        """Walk up the parent chain looking for a Workspace instance."""
        w = self.parentWidget()
        while w is not None:
            if w.__class__.__name__ == "Workspace":
                return w
            w = w.parentWidget()
        return None

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        tabs = QTabWidget()
        root.addWidget(tabs, stretch=1)

        self.back_button = QPushButton(t("detail.back"))
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(self._on_back_clicked)

        # ===== Overview tab (scrollable) =====
        overview_scroll = QScrollArea()
        overview_scroll.setWidgetResizable(True)
        overview_scroll.setFrameShape(QFrame.Shape.NoFrame)

        overview = QWidget()
        ov = QVBoxLayout(overview)
        ov.setContentsMargins(0, SPACING["lg"], 0, 0)
        ov.setSpacing(SPACING["lg"])
        overview_scroll.setWidget(overview)

        # Player card + action buttons
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

        # Subscriptions card
        self.sub_card = SectionCard(title=t("detail.sub.group"))

        self.sub_table = make_standard_table(
            headers=[
                t("detail.sub.col.activity"),
                t("detail.sub.col.plan"),
                t("detail.sub.col.sessions"),
                t("detail.sub.col.expires"),
                t("detail.sub.col.days"),
            ],
            column_modes=["stretch"] * 5,
            parent=self,
        )
        self.sub_table.verticalHeader().setDefaultSectionSize(32)
        self.sub_table.horizontalHeader().setFixedHeight(34)
        self.sub_table.itemSelectionChanged.connect(self._on_sub_selection_changed)
        self.sub_table.setMinimumHeight(150)
        self.sub_table.setMaximumHeight(260)
        self.sub_card.body.addWidget(self.sub_table)

        self.sub_empty_label = QLabel(t("detail.sub.none_active"))
        self.sub_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_empty_label.setWordWrap(True)
        self.sub_empty_label.setSizePolicy(
            self.sub_empty_label.sizePolicy().horizontalPolicy(),
            self.sub_empty_label.sizePolicy().verticalPolicy().Maximum,
        )
        self.sub_card.body.addWidget(self.sub_empty_label)

        self.sub_card.body.addSpacing(SPACING["sm"])

        sub_buttons = QHBoxLayout()
        sub_buttons.setSpacing(SPACING["sm"])
        sub_buttons.setContentsMargins(0, 0, 0, 0)

        self.activate_button = QPushButton(t("detail.sub.activate"))
        self.suspend_button = QPushButton(t("detail.sub.suspend"))
        make_warning(self.suspend_button)
        self.record_payment_button = QPushButton(t("detail.sub.record_payment"))
        make_secondary(self.record_payment_button)

        self.edit_sub_button = QPushButton(t("detail.sub.edit"))
        make_secondary(self.edit_sub_button)
        self.edit_sub_button.setEnabled(False)

        self.delete_sub_button = QPushButton(t("detail.sub.delete"))
        make_danger(self.delete_sub_button)
        self.delete_sub_button.setEnabled(False)

        self.activate_button.clicked.connect(self._on_activate_subscription)
        self.suspend_button.clicked.connect(self._on_suspend_subscription)
        self.record_payment_button.clicked.connect(self._on_record_payment)
        self.edit_sub_button.clicked.connect(self._on_edit_subscription)
        self.delete_sub_button.clicked.connect(self._on_delete_subscription)

        sub_buttons.addWidget(self.activate_button)
        sub_buttons.addWidget(self.suspend_button)
        sub_buttons.addWidget(self.record_payment_button)
        sub_buttons.addWidget(self.edit_sub_button)
        sub_buttons.addWidget(self.delete_sub_button)
        sub_buttons.addStretch()
        
        sub_buttons_widget = QWidget()
        sub_buttons_widget.setLayout(sub_buttons)
        sub_buttons_widget.setSizePolicy(
            sub_buttons_widget.sizePolicy().horizontalPolicy(),
            sub_buttons_widget.sizePolicy().verticalPolicy().Fixed,
        )
        self.sub_card.body.addWidget(sub_buttons_widget)

        self.sub_card.setMinimumHeight(260)
        ov.addWidget(self.sub_card)

        # Notes card
        self.notes_card = SectionCard(title=t("detail.notes.group"))
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(90)
        save_notes_button = QPushButton(t("detail.notes.save"))
        make_secondary(save_notes_button)
        save_notes_button.clicked.connect(self._on_save_notes)
        self.notes_card.body.addWidget(self.notes_input)
        notes_footer = QHBoxLayout()
        notes_footer.addStretch()
        notes_footer.addWidget(save_notes_button)
        self.notes_card.body.addLayout(notes_footer)
        ov.addWidget(self.notes_card)
        ov.addStretch()

        tabs.addTab(overview_scroll, t("detail.tab.overview"))

        # ===== Attendance tab (scrollable) =====
        attendance_scroll = QScrollArea()
        attendance_scroll.setWidgetResizable(True)
        attendance_scroll.setFrameShape(QFrame.Shape.NoFrame)

        attendance = QWidget()
        att = QVBoxLayout(attendance)
        att.setContentsMargins(0, SPACING["lg"], 0, 0)
        att.setSpacing(SPACING["lg"])

        self.att_card = SectionCard(title=t("detail.att.group"))
        self.attendance_table = make_standard_table(
            headers=[
                t("detail.att.col.datetime"),
                t("detail.att.col.result"),
                t("detail.att.col.reason"),
                t("detail.att.col.override"),
                t("detail.att.col.recorded_by"),
            ],
            column_modes=["stretch"] * 5,
            parent=self,
        )
        self.attendance_table.setMinimumHeight(200)
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

        att_buttons_widget = QWidget()
        att_buttons_widget.setLayout(att_buttons)
        att_buttons_widget.setSizePolicy(
            att_buttons_widget.sizePolicy().horizontalPolicy(),
            att_buttons_widget.sizePolicy().verticalPolicy().Fixed,
        )
        self.att_card.body.addWidget(att_buttons_widget)
        att.addWidget(self.att_card)
        att.addStretch()

        attendance_scroll.setWidget(attendance)
        tabs.addTab(attendance_scroll, t("detail.tab.attendance"))

        # ===== Records & Activity tab (scrollable) =====
        records_scroll = QScrollArea()
        records_scroll.setWidgetResizable(True)
        records_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.records_tab = PlayerRecordsTab(self.player_id, player_name="")
        records_scroll.setWidget(self.records_tab)
        tabs.addTab(records_scroll, t("detail.tab.records"))

    # ---------- theming ----------

    def restyle(self):
        tm = theme()
        self.sub_empty_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  padding: 12px;"
            f"  font-style: italic;"
            f"}}"
        )

        # Apply clear selection styling to both tables
        selection_qss = (
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
        self.sub_table.setStyleSheet(selection_qss)
        self.attendance_table.setStyleSheet(selection_qss)

        if hasattr(self, "_active_subs"):
            self._render_sub_table()

    # ---------- data ----------

    def refresh(self):
        player = players_repo.get_by_id(self.player_id)
        if player is None:
            return
        self.current_player = player

        active = subscription_service.get_all_active(self.player_id)
        suspended = subscription_service.get_suspended(self.player_id)
        self._active_subs = active + suspended

        most_recent = active[0] if active else None
        display = subscription_service.get_display_status(self.player_id)

        self.player_card.display_player(
            player, most_recent, check_in_state=None, display=display,
        )
        self._render_sub_table()

        self.notes_input.setPlainText(player.notes or "")
        self._load_attendance()
        if hasattr(self, "records_tab"):
            self.records_tab.player_name = player.full_name
            self.records_tab.refresh()

    def _render_sub_table(self):
        subs = self._active_subs
        if not subs:
            self.sub_table.hide()
            self.sub_empty_label.show()
            self._on_sub_selection_changed()
            return

        self.sub_table.show()
        self.sub_empty_label.hide()

        tm = theme()
        self.sub_table.blockSignals(True)
        self.sub_table.setRowCount(len(subs))

        for i, sub in enumerate(subs):
            is_suspended = (sub.status == "suspended")
            dim_color = QColor(tm.color("text_secondary"))

            act = activity_service.get(sub.activity_id) if sub.activity_id else None
            act_name = activity_service.get_localized_name(act) if act else "—"
            if is_suspended:
                act_name = f"⏸ {act_name}"
            act_item = QTableWidgetItem(act_name)
            if is_suspended:
                act_item.setForeground(dim_color)
            self.sub_table.setItem(i, 0, act_item)

            if sub.plan_type:
                plan_label = get_plan_label(sub.plan_type)
            else:
                plan_label = t("detail.sub.custom")
            plan_item = QTableWidgetItem(plan_label)
            if is_suspended:
                plan_item.setForeground(dim_color)
            self.sub_table.setItem(i, 1, plan_item)

            sess_item = QTableWidgetItem(f"{sub.sessions_remaining} / {sub.sessions_total}")
            if is_suspended:
                sess_item.setForeground(dim_color)
            self.sub_table.setItem(i, 2, sess_item)

            exp_item = QTableWidgetItem(sub.expiry_date)
            if is_suspended:
                exp_item.setForeground(dim_color)
            self.sub_table.setItem(i, 3, exp_item)

            days = ", ".join(t(f"weekday.{d.lower()}") for d in (sub.allowed_days or []))
            days_item = QTableWidgetItem(days)
            if is_suspended:
                days_item.setForeground(dim_color)
            self.sub_table.setItem(i, 4, days_item)

        self.sub_table.blockSignals(False)

        if subs:
            self.sub_table.selectRow(0)

        self._on_sub_selection_changed()

    def _selected_sub(self):
        rows = self.sub_table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._active_subs):
            return self._active_subs[idx]
        return None

    def _on_sub_selection_changed(self):
        sub = self._selected_sub()
        has_sel = sub is not None

        # Suspend/Reactivate logic
        if has_sel and sub.status == "suspended":
            self.suspend_button.setText(t("detail.sub.reactivate"))
            self.suspend_button.setEnabled(True)
        elif has_sel and sub.status == "active":
            self.suspend_button.setText(t("detail.sub.suspend"))
            self.suspend_button.setEnabled(True)
        else:
            self.suspend_button.setText(t("detail.sub.suspend"))
            self.suspend_button.setEnabled(False)

        self.record_payment_button.setEnabled(has_sel)
        self.edit_sub_button.setEnabled(has_sel)
        self.delete_sub_button.setEnabled(has_sel)

    def _on_edit_subscription(self):
        sub = self._selected_sub()
        if sub is None:
            return

        fresh = subscriptions_repo.get_by_id(sub.subscription_id)
        if fresh is None:
            warn(self,
                 t("detail.sub.edit"),
                 t("detail.msg.player_not_found"))
            return

        dlg = EditSubscriptionDialog(fresh, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_delete_subscription(self):
        """Move the selected subscription to the recycle bin."""
        sub = self._selected_sub()
        if sub is None:
            return

        confirmed = ask(
            self,
            t("detail.sub.delete_confirm.title"),
            t("detail.sub.delete_confirm.body"),
        )
        if not confirmed:
            return

        try:
            from services import archive_service
            archive_service.archive_subscription(sub.subscription_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to archive subscription"
            )
            warn(
                self,
                t("detail.sub.delete_failed.title"),
                t("detail.sub.delete_failed.body", error=str(e)),
            )
            return

        self.refresh()

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
        self._uninstall_header_action()
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
        sub = self._selected_sub()
        if sub is None:
            return
            
        if sub.status == "suspended":
            # Reactivate
            if ask(self, t("detail.msg.reactivate_title"), t("detail.msg.reactivate_body")):
                subscriptions_repo.set_status(sub.subscription_id, "active")
                audit_service.record(
                    "subscription.reactivate",
                    target_type="subscription",
                    target_id=sub.subscription_id
                )
                self.refresh()
        else:
            # Suspend
            if ask(self, t("detail.msg.suspend_title"), t("detail.msg.suspend_body")):
                subscription_service.suspend(sub.subscription_id)
                audit_service.subscription_suspended(subscription_id=sub.subscription_id)
                self.refresh()

    def _on_record_payment(self):
        sub = self._selected_sub()
        if sub is None:
            info(self, t("detail.msg.no_sub_title"), t("detail.msg.no_sub_msg"))
            return
        current_amount = sub.payment_amount or 0.0
        dialog = UpdatePaymentDialog(current_amount, parent=self)
        if dialog.exec():
            amount, payment_date = dialog.get_values()
            subscription_service.record_payment(sub.subscription_id, amount, payment_date)
            audit_service.payment_recorded(
                subscription_id=sub.subscription_id,
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
                log_id=entry.log_id, player_id=self.player_id
            )
            self.refresh()
        else:
            warn(self, t("detail.att.undo_failed_title"), t("detail.att.undo_failed_msg"))

    def _on_manual_check_in(self):
        outcome = perform_check_in(self.player_id, parent_widget=self)
        if outcome is None:
            warn(self, t("checkin.unknown_player_title"),
                 t("detail.msg.player_not_found"))
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
                self.player_id,
                parent_widget=self,
                preselect_subscription_id=picker.chosen_subscription_id,
            )
            if outcome is None:
                return

        if outcome.checked_in:
            audit_service.manual_checkin(player_id=self.player_id)

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