"""
Recycle bin screen.
"""

from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTabWidget, QTableWidgetItem, QDialog, QLineEdit,
)
from qtpy.QtCore import Qt,QTimer

from repositories import subscriptions_repo, players_repo
from services import archive_service, activity_service
from config.config_loader import get_plan_label
from ui.table_helpers import make_standard_table
from ui.components import EmptyState
from ui.theme import theme, ThemedWidget, make_danger, make_secondary, make_warning
from ui.design import SPACING
from ui.i18n import t
from ui.message_box import ask, warn, info


class RecycleBinScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._dirty = True
        self._build_ui()
        self._init_theme()

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self._dirty = False
            QTimer.singleShot(0, self.refresh)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._dirty = True

    def restyle(self):
        tm = theme()
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
        if hasattr(self, "players_table"):
            self.players_table.setStyleSheet(selection_qss)
            self.subs_table.setStyleSheet(selection_qss)
            self.users_table.setStyleSheet(selection_qss)
            self.acts_table.setStyleSheet(selection_qss)
        if hasattr(self, "champs_table"):
            self.champs_table.setStyleSheet(selection_qss)
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        toolbar = QHBoxLayout()
        toolbar.setSpacing(SPACING["sm"])
        self.empty_button = QPushButton(t("recycle.empty_btn"))
        make_danger(self.empty_button)
        self.empty_button.clicked.connect(self._on_empty_bin)
        toolbar.addWidget(self.empty_button)
        toolbar.addStretch()
        root.addLayout(toolbar)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, stretch=1)

        # ===== Tab 1: Archived Players =====
        players_tab = QWidget()
        pt_layout = QVBoxLayout(players_tab)
        pt_layout.setContentsMargins(0, SPACING["md"], 0, 0)

        self.players_table = make_standard_table(
            headers=[
                t("recycle.col.name"),
                t("recycle.col.id"),
                t("recycle.col.archived_at"),
            ],
            column_modes=["stretch", "resize", "resize"],
            parent=self,
        )
        self.players_table.itemSelectionChanged.connect(self._update_buttons)
        pt_layout.addWidget(self.players_table)

        self.players_empty = EmptyState(icon="🗑", message=t("recycle.empty_players"))
        self.players_empty.hide()
        pt_layout.addWidget(self.players_empty, stretch=1)

        p_btns = QHBoxLayout()
        p_btns.addStretch()
        self.restore_player_btn = QPushButton(t("recycle.btn_restore"))
        self.restore_player_btn.setEnabled(False)
        self.restore_player_btn.clicked.connect(self._on_restore_player)

        self.delete_player_btn = QPushButton(t("recycle.btn_delete_forever"))
        make_danger(self.delete_player_btn)
        self.delete_player_btn.setEnabled(False)
        self.delete_player_btn.clicked.connect(self._on_delete_player)

        p_btns.addWidget(self.restore_player_btn)
        p_btns.addWidget(self.delete_player_btn)
        pt_layout.addLayout(p_btns)

        self.tabs.addTab(players_tab, t("recycle.tab_players"))

        # ===== Tab 2: Archived Subscriptions =====
        subs_tab = QWidget()
        st_layout = QVBoxLayout(subs_tab)
        st_layout.setContentsMargins(0, SPACING["md"], 0, 0)

        self.subs_table = make_standard_table(
            headers=[
                t("recycle.col.player"),
                t("recycle.col.activity"),
                t("recycle.col.plan"),
                t("recycle.col.archived_at"),
            ],
            column_modes=["stretch", "resize", "resize", "resize"],
            parent=self,
        )
        self.subs_table.itemSelectionChanged.connect(self._update_buttons)
        st_layout.addWidget(self.subs_table)

        self.subs_empty = EmptyState(icon="🗑", message=t("recycle.empty_subs"))
        self.subs_empty.hide()
        st_layout.addWidget(self.subs_empty, stretch=1)

        s_btns = QHBoxLayout()
        s_btns.addStretch()
        self.restore_sub_btn = QPushButton(t("recycle.btn_restore"))
        self.restore_sub_btn.setEnabled(False)
        self.restore_sub_btn.clicked.connect(self._on_restore_sub)

        self.delete_sub_btn = QPushButton(t("recycle.btn_delete_forever"))
        make_danger(self.delete_sub_btn)
        self.delete_sub_btn.setEnabled(False)
        self.delete_sub_btn.clicked.connect(self._on_delete_sub)

        s_btns.addWidget(self.restore_sub_btn)
        s_btns.addWidget(self.delete_sub_btn)
        st_layout.addLayout(s_btns)

        self.tabs.addTab(subs_tab, t("recycle.tab_subs"))

        # ===== Tab 3: Archived Users =====
        users_tab = QWidget()
        ut_layout = QVBoxLayout(users_tab)
        ut_layout.setContentsMargins(0, SPACING["md"], 0, 0)

        self.users_table = make_standard_table(
            headers=[
                t("recycle.col.id"),
                t("recycle.col.name"),
                t("recycle.col.username"),
            ],
            column_modes=["resize", "stretch", "stretch"],
            parent=self,
        )
        self.users_table.itemSelectionChanged.connect(self._update_buttons)
        ut_layout.addWidget(self.users_table)

        self.users_empty = EmptyState(icon="🗑", message=t("recycle.empty_users"))
        self.users_empty.hide()
        ut_layout.addWidget(self.users_empty, stretch=1)

        u_btns = QHBoxLayout()
        u_btns.addStretch()
        self.restore_user_btn = QPushButton(t("recycle.btn_restore"))
        self.restore_user_btn.setEnabled(False)
        self.restore_user_btn.clicked.connect(self._on_restore_user)

        self.delete_user_btn = QPushButton(t("recycle.btn_delete_forever"))
        make_danger(self.delete_user_btn)
        self.delete_user_btn.setEnabled(False)
        self.delete_user_btn.hide() 

        u_btns.addWidget(self.restore_user_btn)
        u_btns.addWidget(self.delete_user_btn)
        ut_layout.addLayout(u_btns)

        self.tabs.addTab(users_tab, t("recycle.tab_users"))
        self.tabs.currentChanged.connect(self._update_buttons)
        
                # ===== Tab 4: Archived Activities =====
        acts_tab = QWidget()
        at_layout = QVBoxLayout(acts_tab)
        at_layout.setContentsMargins(0, SPACING["md"], 0, 0)

        self.acts_table = make_standard_table(
            headers=[t("activities.col.name"), t("recycle.col.archived_at")],
            column_modes=["stretch", "resize"],
            parent=self,
        )
        self.acts_table.itemSelectionChanged.connect(self._update_buttons)
        at_layout.addWidget(self.acts_table)

        self.acts_empty = EmptyState(icon="🗑", message=t("recycle.empty_activities"))        
        self.acts_empty.hide()
        at_layout.addWidget(self.acts_empty, stretch=1)

        a_btns = QHBoxLayout()
        a_btns.addStretch()
        self.restore_act_btn = QPushButton(t("recycle.btn_restore"))
        self.restore_act_btn.setEnabled(False)
        self.restore_act_btn.clicked.connect(self._on_restore_act)

        a_btns.addWidget(self.restore_act_btn)
        at_layout.addLayout(a_btns)

        self.tabs.addTab(acts_tab, t("recycle.tab_activities"))

        # ===== Tab 5: Archived Championships =====
        champs_tab = QWidget()
        ct_layout = QVBoxLayout(champs_tab)
        ct_layout.setContentsMargins(0, SPACING["md"], 0, 0)

        self.champs_table = make_standard_table(
            headers=[
                t("recycle.col.name"),
                t("recycle.col.event_date"),
                t("recycle.col.archived_at"),
            ],
            column_modes=["stretch", "resize", "resize"],
            parent=self,
        )
        self.champs_table.itemSelectionChanged.connect(self._update_buttons)
        ct_layout.addWidget(self.champs_table)

        self.champs_empty = EmptyState(
            icon="🗑", message=t("recycle.empty_championships")
        )
        self.champs_empty.hide()
        ct_layout.addWidget(self.champs_empty, stretch=1)

        c_btns = QHBoxLayout()
        c_btns.addStretch()
        self.restore_champ_btn = QPushButton(t("recycle.btn_restore"))
        self.restore_champ_btn.setEnabled(False)
        self.restore_champ_btn.clicked.connect(self._on_restore_champ)

        self.delete_champ_btn = QPushButton(t("recycle.btn_delete_forever"))
        make_danger(self.delete_champ_btn)
        self.delete_champ_btn.setEnabled(False)
        self.delete_champ_btn.clicked.connect(self._on_delete_champ)

        c_btns.addWidget(self.restore_champ_btn)
        c_btns.addWidget(self.delete_champ_btn)
        ct_layout.addLayout(c_btns)

        self.tabs.addTab(champs_tab, t("recycle.tab_championships"))
    def refresh(self):
        contents = archive_service.get_recycle_bin_contents()

        players = contents["players"]
        subs = contents["subscriptions"]

        from repositories import users_repo
        users = users_repo.list_tombstoned()

        from repositories import activities_repo
        acts = activities_repo.list_archived()

        from repositories import championships_repo
        champs = championships_repo.list_championships(include_archived=True)
        # list_championships(include_archived=True) returns ALL rows —
        # filter to only the archived ones for the recycle bin tab.
        champs = [c for c in champs if c.archived_at is not None]

        # Tab labels with live counts (translated).
        self.tabs.setTabText(0, f"{t('recycle.tab_players')} ({len(players)})")
        self.tabs.setTabText(1, f"{t('recycle.tab_subs')} ({len(subs)})")
        self.tabs.setTabText(2, f"{t('recycle.tab_users')} ({len(users)})")
        self.tabs.setTabText(3, f"{t('recycle.tab_activities')} ({len(acts)})")
        self.tabs.setTabText(4, f"{t('recycle.tab_championships')} ({len(champs)})")

        # Enable "Empty Bin" whenever ANY tab has content.
        # Note: empty_recycle_bin() currently only empties players + subs,
        # so this button still won't purge users/activities/championships
        # — but at least it's not lying by staying greyed out when the
        # only thing in the bin is a user or an activity.
        any_content = (
            len(players) > 0
            or len(subs) > 0
            or len(acts) > 0
            or len(champs) > 0
        )
        self.empty_button.setEnabled(any_content)

        # Render each tab.
        self._render_players(players)
        self._render_subs(subs)
        self._render_users(users)
        self._render_acts(acts)
        self._render_champs(champs)

    def _render_acts(self, acts):
        self.acts_table.setRowCount(len(acts))
        if not acts:
            self.acts_table.hide()
            self.acts_empty.show()
            return
        self.acts_table.show()
        self.acts_empty.hide()
        for i, a in enumerate(acts):
            name_item = QTableWidgetItem(a.name)
            name_item.setData(Qt.ItemDataRole.UserRole, a.activity_id)
            self.acts_table.setItem(i, 0, name_item)
            self.acts_table.setItem(i, 1, QTableWidgetItem(a.archived_at or "—"))
            


    def _on_restore_act(self):
        rows = self.acts_table.selectionModel().selectedRows()
        if not rows: return
        aid = self.acts_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if aid is not None:
            from repositories import activities_repo
            activities_repo.restore(aid)
            QTimer.singleShot(0, self.refresh)


    def _render_champs(self, champs):
        self.champs_table.setRowCount(len(champs))
        if not champs:
            self.champs_table.hide()
            self.champs_empty.show()
            return

        self.champs_table.show()
        self.champs_empty.hide()

        for i, c in enumerate(champs):
            name_item = QTableWidgetItem(c.name or "—")
            name_item.setData(Qt.ItemDataRole.UserRole, c.championship_id)
            self.champs_table.setItem(i, 0, name_item)
            self.champs_table.setItem(
                i, 1, QTableWidgetItem(c.event_date or "—")
            )
            self.champs_table.setItem(
                i, 2, QTableWidgetItem(c.archived_at or "—")
            )

    def _selected_champ_id(self):
        rows = self.champs_table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.champs_table.item(rows[0].row(), 0).data(
            Qt.ItemDataRole.UserRole
        )

    def _on_restore_champ(self):
        cid = self._selected_champ_id()
        if cid is None:
            return
        try:
            from repositories import championships_repo
            championships_repo.restore_championship(cid)
            QTimer.singleShot(0, self.refresh)
        except Exception as e:
            warn(self, t("recycle.err_title"), str(e))

    def _on_delete_champ(self):
        cid = self._selected_champ_id()
        if cid is None:
            return
        dlg = _TypedConfirmDialog(
            self,
            t("recycle.confirm_delete_champ_title"),
            t("recycle.confirm_delete_champ_body"),
        )
        if dlg.exec() == dlg.DialogCode.Accepted:
            try:
                from repositories import championships_repo
                championships_repo.delete_championship(cid)
                QTimer.singleShot(0, self.refresh)
            except Exception as e:
                warn(self, t("recycle.err_title"), str(e))

    def _render_users(self, users):
        self.users_table.setRowCount(len(users))
        if not users:
            self.users_table.hide()
            self.users_empty.show()
            return

        self.users_table.show()
        self.users_empty.hide()

        for i, u in enumerate(users):
            # ID
            id_item = QTableWidgetItem(str(u.user_id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.users_table.setItem(i, 0, id_item)
            
            # Name
            name_item = QTableWidgetItem(u.display_name or "?")
            name_item.setData(Qt.ItemDataRole.UserRole, u.user_id)
            self.users_table.setItem(i, 1, name_item)
            
            # Username
            self.users_table.setItem(i, 2, QTableWidgetItem(u.username))

    def _render_players(self, players):
        self.players_table.setRowCount(len(players))
        if not players:
            self.players_table.hide()
            self.players_empty.show()
            return

        self.players_table.show()
        self.players_empty.hide()

        for i, p in enumerate(players):
            name_item = QTableWidgetItem(p.full_name or "?")
            name_item.setData(Qt.ItemDataRole.UserRole, p.player_id)
            self.players_table.setItem(i, 0, name_item)

            id_item = QTableWidgetItem(str(p.player_id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.players_table.setItem(i, 1, id_item)
            self.players_table.setItem(i, 2, QTableWidgetItem(p.archived_at or "—"))

    def _render_subs(self, subs):
        self.subs_table.setRowCount(len(subs))
        if not subs:
            self.subs_table.hide()
            self.subs_empty.show()
            return

        self.subs_table.show()
        self.subs_empty.hide()

        player_ids = set(s.player_id for s in subs)
        player_map = {pid: players_repo.get_by_id(pid) for pid in player_ids}

        for i, s in enumerate(subs):
            player = player_map.get(s.player_id)
            p_name = player.full_name if player else f"#{s.player_id}"
            name_item = QTableWidgetItem(p_name)
            name_item.setData(Qt.ItemDataRole.UserRole, s.subscription_id)
            self.subs_table.setItem(i, 0, name_item)

            act = activity_service.get(s.activity_id) if s.activity_id else None
            act_name = activity_service.get_localized_name(act) if act else "—"
            self.subs_table.setItem(i, 1, QTableWidgetItem(act_name))

            plan = get_plan_label(s.plan_type) if s.plan_type else t("detail.sub.custom")
            self.subs_table.setItem(i, 2, QTableWidgetItem(plan))

            self.subs_table.setItem(i, 3, QTableWidgetItem(s.archived_at or "—"))

    def _update_buttons(self):
        idx = self.tabs.currentIndex()
        if idx == 0:
            has = bool(self.players_table.selectionModel().selectedRows())
            self.restore_player_btn.setEnabled(has)
            self.delete_player_btn.setEnabled(has)
        elif idx == 1:
            has = bool(self.subs_table.selectionModel().selectedRows())
            self.restore_sub_btn.setEnabled(has)
            self.delete_sub_btn.setEnabled(has)
        elif idx == 2:
            has = bool(self.users_table.selectionModel().selectedRows())
            self.restore_user_btn.setEnabled(has)
        elif idx == 3:
            has = bool(self.acts_table.selectionModel().selectedRows())
            self.restore_act_btn.setEnabled(has)
        elif idx == 4:
            has = bool(self.champs_table.selectionModel().selectedRows())
            self.restore_champ_btn.setEnabled(has)
            self.delete_champ_btn.setEnabled(has)

    def _selected_player_id(self):
        rows = self.players_table.selectionModel().selectedRows()
        return self.players_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole) if rows else None

    def _selected_sub_id(self):
        rows = self.subs_table.selectionModel().selectedRows()
        return self.subs_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole) if rows else None

    def _on_restore_player(self):
        pid = self._selected_player_id()
        if pid is not None:
            try:
                archive_service.restore_player(pid)
                QTimer.singleShot(0, self.refresh)
            except Exception as e:
                warn(self, t("recycle.err_title"), str(e))

    def _on_restore_user(self):
        rows = self.users_table.selectionModel().selectedRows()
        if not rows:
            return
        # FIXED: Get ID from column 1 (where we stored it)
        uid = self.users_table.item(rows[0].row(), 1).data(Qt.ItemDataRole.UserRole)
        if uid is None:
            return
            
        from repositories import users_repo
        from qtpy.QtWidgets import QInputDialog
        from ui.message_box import warn
        
        new_username, ok = QInputDialog.getText(
            self, 
            t("users.restore.title"), 
            t("users.restore.prompt"),
            text=f"user{uid}"
        )
        
        if not ok or not new_username.strip():
            return
            
        try:
            users_repo.restore_tombstoned(uid, new_username.strip(), t("users.restore.display_name"))
            QTimer.singleShot(0, self.refresh)
        except Exception as e:
            warn(self, t("recycle.err_title"), str(e))

    def _on_delete_player(self):
        pid = self._selected_player_id()
        if pid is not None:
            dlg = _TypedConfirmDialog(self, t("recycle.confirm_delete_player_title"), t("recycle.confirm_delete_player_body"))
            if dlg.exec() == dlg.DialogCode.Accepted:
                try:
                    archive_service.permanently_delete_player(pid)
                    QTimer.singleShot(0, self.refresh)
                except Exception as e:
                    warn(self, t("recycle.err_title"), str(e))

    def _on_restore_sub(self):
        sid = self._selected_sub_id()
        if sid is not None:
            try:
                archive_service.restore_subscription(sid)
                QTimer.singleShot(0, self.refresh)
            except Exception as e:
                warn(self, t("recycle.err_title"), str(e))

    def _on_delete_sub(self):
        sid = self._selected_sub_id()
        if sid is not None:
            dlg = _TypedConfirmDialog(self, t("recycle.confirm_delete_sub_title"), t("recycle.confirm_delete_sub_body"))
            if dlg.exec() == dlg.DialogCode.Accepted:
                try:
                    archive_service.permanently_delete_subscription(sid)
                    QTimer.singleShot(0, self.refresh)
                except Exception as e:
                    warn(self, t("recycle.err_title"), str(e))

    def _on_empty_bin(self):
        # Guard: even if the button is somehow enabled while empty, do
        # nothing rather than bothering the user with a confirm dialog.
        if not self.empty_button.isEnabled():
            return
        if ask(self, t("recycle.confirm_empty_title"), t("recycle.confirm_empty_body")):
            # Disable immediately to prevent double-clicks while the
            # (potentially slow) purge runs. refresh() will re-enable
            # it if the bin is still non-empty afterwards.
            self.empty_button.setEnabled(False)
            self.empty_button.repaint()
            try:
                summary = archive_service.empty_recycle_bin()
                info(self, t("recycle.empty_done_title"),
                     t("recycle.empty_done_body",
                          players=summary["players"],
                          subs=summary["subscriptions"]))
                QTimer.singleShot(0, self.refresh)
            except Exception as e:
                warn(self, t("recycle.err_title"), str(e))
                # Re-enable on error so the user can retry.
                self.empty_button.setEnabled(True)

class _TypedConfirmDialog(ThemedWidget, QDialog):
    def __init__(self, parent, title, body):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        lbl = QLabel(body)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.input = QLineEdit()
        self.input.setPlaceholderText("DELETE")
        self.input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton(t("recycle.btn_cancel"))
        make_secondary(cancel)
        cancel.clicked.connect(self.reject)

        self.confirm_btn = QPushButton(t("recycle.btn_delete_forever"))
        make_danger(self.confirm_btn)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel)
        btn_row.addWidget(self.confirm_btn)
        layout.addLayout(btn_row)
        self._init_theme()

    def _on_text_changed(self, text):
        self.confirm_btn.setEnabled(text.strip().upper() == "DELETE")