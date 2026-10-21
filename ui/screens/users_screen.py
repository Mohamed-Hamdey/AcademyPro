"""
Users management screen — v4 design.
"""

import os
import sys

from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QLabel,QSizePolicy
)
from ui.message_box import warn, ask
from qtpy.QtCore import Qt, QSize
from qtpy.QtGui import QPixmap, QColor, QPainter, QBrush, QFont, QIcon
from ui.utils import Debouncer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import users_repo
from repositories.users_repo import User
from services import audit_service, auth_service
from ui.components import Toolbar, SectionCard, Pill
from ui.dialogs.user_form_dialog import UserFormDialog
from ui.screens.change_password_dialog import ChangePasswordDialog
from ui.theme import make_warning, theme, ThemedWidget, make_secondary, make_danger
from ui.design import SPACING, RADIUS
from ui.i18n import t
from app_state import app as app_state
from ui.table_helpers import make_standard_table


_AVATAR_SIZE = 32

def _role_color(role: str) -> str:
    tm = theme()
    return tm.color("primary") if role == "manager" else tm.color("success")


def _make_initial_avatar(display_name: str, role: str) -> QPixmap:
    letter = (display_name or "?").strip()[:1].upper() or "?"
    pix = QPixmap(_AVATAR_SIZE, _AVATAR_SIZE)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setBrush(QBrush(QColor(_role_color(role))))
    p.setPen(Qt.PenStyle.NoPen)
    radius = _AVATAR_SIZE // 2
    p.drawRoundedRect(0, 0, _AVATAR_SIZE, _AVATAR_SIZE, radius, radius)
    p.setPen(QColor("#FFFFFF"))
    f = QFont()
    f.setPixelSize(16)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    p.end()

    return pix


def _avatar_pixmap(user: User) -> QPixmap:
    path = user.photo_path
    if path and os.path.exists(path):
        src = QPixmap(path)
        if not src.isNull():
            scaled = src.scaled(
                _AVATAR_SIZE, _AVATAR_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            w, h = scaled.width(), scaled.height()
            if w > _AVATAR_SIZE or h > _AVATAR_SIZE:
                x = max(0, (w - _AVATAR_SIZE) // 2)
                y = max(0, (h - _AVATAR_SIZE) // 2)
                scaled = scaled.copy(x, y, _AVATAR_SIZE, _AVATAR_SIZE)
            return scaled
    return _make_initial_avatar(user.display_name, user.role)


class UsersScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._rows = []
        self._search_debouncer = Debouncer(250, self.refresh, parent=self)
        self._loaded = False
        self._build_ui()
        self._init_theme()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        self.toolbar = Toolbar()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("users.search_placeholder"))
        self.search_input.setProperty("cssClass", "search")
        self.search_input.setMinimumWidth(240)
        self.search_input.textChanged.connect(self._search_debouncer.trigger)
        
        self.add_button = QPushButton(t("users.add"))
        self.add_button.clicked.connect(self._on_add)

        self.toolbar.add_leading(self.search_input, stretch=1)
        self.toolbar.add_trailing(self.add_button)
        root.addWidget(self.toolbar)

        self.table_card = SectionCard(title=t("users.title"))
        # FIX 1: Make the SectionCard expand to fill vertical space
        self.table_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, 
            QSizePolicy.Policy.Expanding
        )

        self.table = make_standard_table(
            headers=[
                t("users.col.photo"),
                t("users.col.username"),
                t("users.col.display_name"),
                t("users.col.role"),
                t("users.col.status"),
                t("users.col.last_login"),
            ],
            column_modes=["fixed", "stretch", "stretch", "resize", "resize", "resize"],
            parent=self,
        )
        self.table.setColumnWidth(0, 48)
        self.table.setIconSize(QSize(_AVATAR_SIZE, _AVATAR_SIZE))
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        
        # FIX 2: Ensure the table itself also stretches inside the card
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)

        self.table_card.body.addWidget(self.table, stretch=1) # <-- added stretch=1
        self.table_card.body.addSpacing(SPACING["sm"])

        action_row = QHBoxLayout()
        action_row.setSpacing(SPACING["sm"])

        self.change_pw_button = QPushButton(t("users.action.change_password"))
        make_secondary(self.change_pw_button)
        self.change_pw_button.clicked.connect(self._on_change_password)
        self.change_pw_button.setEnabled(False)

        self.toggle_active_button = QPushButton(t("users.action.deactivate"))
        make_warning(self.toggle_active_button)
        self.toggle_active_button.clicked.connect(self._on_toggle_active)
        self.toggle_active_button.setEnabled(False)

        self.delete_user_button = QPushButton(t("users.action.delete"))
        make_danger(self.delete_user_button)
        self.delete_user_button.clicked.connect(self._on_delete_user)
        self.delete_user_button.setEnabled(False)

        action_row.addStretch()
        action_row.addWidget(self.change_pw_button)
        action_row.addWidget(self.toggle_active_button)
        action_row.addWidget(self.delete_user_button)
        self.table_card.body.addLayout(action_row)

        # FIX 3: Give the card the remaining vertical space, and 
        # REMOVE the trailing stretch that was squashing the table.
        root.addWidget(self.table_card, stretch=1)
        # root.addStretch()  <-- REMOVED

    def restyle(self):
        tm = theme()
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
        if hasattr(self, "_rows"):
            self._render_rows(self._rows)

    def refresh(self):
        prev = self._selected_user()
        prev_id = prev.user_id if prev else None

        query = self.search_input.text().strip()
        rows = users_repo.search(query) if query else users_repo.list_all()
        
        # Hide tombstoned users
        rows = [u for u in rows if not u.username.startswith("deleted_")]
        
        self._rows = rows
        self._render_rows(rows)

        if prev_id is not None:
            for i, u in enumerate(rows):
                if u.user_id == prev_id:
                    self.table.selectRow(i)
                    break

    def _render_rows(self, users: list[User]):
        self.table.setRowCount(len(users))
        tm = theme()

        for i, user in enumerate(users):
            avatar_item = QTableWidgetItem()
            avatar_item.setIcon(QIcon(_avatar_pixmap(user)))
            avatar_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 0, avatar_item)

            self.table.setItem(i, 1, QTableWidgetItem(user.username))
            self.table.setItem(i, 2, QTableWidgetItem(user.display_name))
            self.table.setItem(i, 3, QTableWidgetItem(self._format_role(user.role)))

            active_text = t("users.status.active") if user.active else t("users.status.inactive")
            status_item = QTableWidgetItem(active_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            color = tm.color("success") if user.active else tm.color("text_secondary")
            bg = tm.color("success_soft") if user.active else tm.color("neutral_soft")
            status_item.setForeground(QColor(color))
            status_item.setBackground(QColor(bg))
            self.table.setItem(i, 4, status_item)

            last_login = user.last_login or "—"
            if last_login != "—" and len(last_login) >= 16:
                last_login = last_login[:16]
            self.table.setItem(i, 5, QTableWidgetItem(last_login))

        self._update_action_buttons()

    def _format_role(self, role: str) -> str:
        from ui import i18n
        ar = "المدير" if role == "manager" else "موظف الاستقبال"
        en = "Manager" if role == "manager" else "Receptionist"
        if i18n.current_language() == "ar":
            return f"{ar} · {en}"
        return f"{en} · {ar}"

    def _selected_user(self) -> User:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._rows):
            return None
        return self._rows[idx]

    def _update_action_buttons(self):
        user = self._selected_user()
        has_selection = user is not None

        self.change_pw_button.setEnabled(has_selection)

        toggle_enabled = False
        if has_selection:
            # FIX: If the user is currently active, the action is "Deactivate" (yellow)
            if user.active:
                self.toggle_active_button.setText(t("users.action.deactivate"))
                make_warning(self.toggle_active_button)
                
                is_self = (app_state.user is not None and user.user_id == app_state.user.user_id)
                is_last_manager = (user.role == "manager" and users_repo.count_active_managers() == 1)
                toggle_enabled = not (is_self or is_last_manager)
            else:
                # If inactive, the action is "Activate" (secondary/white)
                self.toggle_active_button.setText(t("users.action.activate"))
                make_warning(self.toggle_active_button)
                toggle_enabled = True

        self.toggle_active_button.setEnabled(toggle_enabled)

        # Can't delete yourself, and can't delete the last manager
        can_delete = has_selection
        if has_selection:
            is_self = (app_state.user is not None and user.user_id == app_state.user.user_id)
            is_last_manager = (user.role == "manager" and users_repo.count_active_managers() == 1)
            if is_self or is_last_manager:
                can_delete = False
        self.delete_user_button.setEnabled(can_delete)

    def _on_delete_user(self):
        user = self._selected_user()
        if user is None:
            return
            
        confirmed = ask(
            self,
            t("users.confirm.delete_title"),
            t("users.confirm.delete_msg", name=user.display_name),
        )
        if not confirmed:
            return
            
        try:
            users_repo.tombstone(user.user_id)
            audit_service.record(
                "user.delete", 
                target_type="user", 
                target_id=user.user_id, 
                details={"username": user.username}
            )
            self.refresh()
        except Exception as e:
            warn(self, t("users.error.delete_failed_title"), str(e))

    def _on_add(self):
        dlg = UserFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _on_row_double_clicked(self, row: int, column: int):
        self._on_edit()

    def _on_edit(self):
        user = self._selected_user()
        if user is None:
            return

        is_last_manager = (
            user.role == "manager"
            and user.active
            and users_repo.count_active_managers() == 1
        )

        dlg = UserFormDialog(user=user, is_last_manager=is_last_manager, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_change_password(self):
        user = self._selected_user()
        if user is None:
            return
        dlg = ChangePasswordDialog(user, force=False, parent=self)
        dlg.exec()

    def _on_toggle_active(self):
        user = self._selected_user()
        if user is None:
            return

        if user.active and app_state.user and user.user_id == app_state.user.user_id:
            warn(self, t("users.error.self_deactivate_title"), t("users.error.self_deactivate_msg"))
            return

        if (user.active and user.role == "manager" and users_repo.count_active_managers() == 1):
            warn(self, t("users.error.last_manager_title"), t("users.error.last_manager_deactivate_msg"))
            return

        target_state = not user.active
        verb = t("users.action.activate") if target_state else t("users.action.deactivate")

        if not ask(self, t("users.confirm.title"), t("users.confirm.toggle_active", name=user.display_name, verb=verb)):
            return

        users_repo.set_active(user.user_id, target_state)
        self.refresh()