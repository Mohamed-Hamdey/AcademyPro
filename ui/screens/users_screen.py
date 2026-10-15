"""
Users management screen — v4 design.

Manager-only. Lists every user, allows:
  * Adding a new user
  * Editing display name, role, active state, photo
  * Changing a user's password
  * Activating / deactivating a user

Safety rules enforced here:
  * The last active manager cannot be deactivated
  * The last active manager cannot be demoted
  * You cannot deactivate your own account
"""

import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QLabel,
)
from ui.message_box import warn, ask
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QColor, QPainter, QBrush, QFont, QIcon

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import users_repo
from repositories.users_repo import User
from services import auth_service
from ui.components import Toolbar, SectionCard, Pill
from ui.dialogs.user_form_dialog import UserFormDialog
from ui.screens.change_password_dialog import ChangePasswordDialog
from ui.theme import theme, ThemedWidget, make_secondary, make_danger
from ui.design import SPACING, RADIUS
from ui.i18n import t
from app_state import app as app_state


_AVATAR_SIZE = 32

# Colors used for avatar fallbacks — one per role, so a user's initial
# is visually distinguishable by role.
def _role_color(role: str) -> str:
    tm = theme()
    return tm.color("primary") if role == "manager" else tm.color("success")


def _make_initial_avatar(display_name: str, role: str) -> QPixmap:
    """
    A rounded square with the first letter of the display name. Colored
    by role. Used when the user has no photo.
    """
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
    """Return either the user's photo (cropped square) or a fallback avatar."""
    path = user.photo_path
    if path and os.path.exists(path):
        src = QPixmap(path)
        if not src.isNull():
            # Scale and crop into a square
            scaled = src.scaled(
                _AVATAR_SIZE, _AVATAR_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Center-crop
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
        self._rows = []       # list of User in the current table order
        self._loaded = False
        self._build_ui()
        # Deferred to first show — see showEvent.
        self._init_theme()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self.refresh()

    # ---------- construction ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        # ---- Toolbar ----
        self.toolbar = Toolbar()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("users.search_placeholder"))
        self.search_input.setProperty("cssClass", "search")
        self.search_input.setMinimumWidth(240)
        self.search_input.textChanged.connect(self.refresh)

        self.add_button = QPushButton(t("users.add"))
        self.add_button.clicked.connect(self._on_add)

        self.toolbar.add_leading(self.search_input, stretch=1)
        self.toolbar.add_trailing(self.add_button)
        root.addWidget(self.toolbar)

        # ---- Table card ----
        self.table_card = SectionCard(title=t("users.title"))

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            t("users.col.photo"),
            t("users.col.username"),
            t("users.col.display_name"),
            t("users.col.role"),
            t("users.col.status"),
            t("users.col.last_login"),
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 48)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setIconSize(QSize(_AVATAR_SIZE, _AVATAR_SIZE))
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)

        self.table_card.body.addWidget(self.table)

        # ---- Action row (inside the card, right-aligned) ----
        self.table_card.body.addSpacing(SPACING["sm"])

        action_row = QHBoxLayout()
        action_row.setSpacing(SPACING["sm"])

        self.change_pw_button = QPushButton(t("users.action.change_password"))
        make_secondary(self.change_pw_button)
        self.change_pw_button.clicked.connect(self._on_change_password)
        self.change_pw_button.setEnabled(False)

        self.toggle_active_button = QPushButton(t("users.action.deactivate"))
        make_danger(self.toggle_active_button)
        self.toggle_active_button.clicked.connect(self._on_toggle_active)
        self.toggle_active_button.setEnabled(False)

        action_row.addStretch()
        action_row.addWidget(self.change_pw_button)
        action_row.addWidget(self.toggle_active_button)
        self.table_card.body.addLayout(action_row)

        # Card hugs its content; leftover space collapses below.
        root.addWidget(self.table_card)
        root.addStretch()

    # ---------- theming ----------

    def restyle(self):
        # Avatars depend on the theme (fallback colors), so refresh
        # the table rows on theme change.
        if hasattr(self, "_rows"):
            self._render_rows(self._rows)

    # ---------- data ----------

    def refresh(self):
        # Preserve selection across refresh, if possible.
        prev = self._selected_user()
        prev_id = prev.user_id if prev else None

        query = self.search_input.text().strip()
        rows = users_repo.search(query) if query else users_repo.list_all()
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
            # Photo (icon)
            avatar_item = QTableWidgetItem()
            avatar_item.setIcon(QIcon(_avatar_pixmap(user)))
            avatar_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 0, avatar_item)

            # Username
            self.table.setItem(i, 1, QTableWidgetItem(user.username))

            # Display name
            self.table.setItem(i, 2, QTableWidgetItem(user.display_name))

            # Role — Arabic · English
            role_text = self._format_role(user.role)
            self.table.setItem(i, 3, QTableWidgetItem(role_text))

            # Status (colored pill text)
            active_text = t("users.status.active") if user.active else t("users.status.inactive")
            status_item = QTableWidgetItem(active_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            color = tm.color("success") if user.active else tm.color("text_secondary")
            bg = tm.color("success_soft") if user.active else tm.color("neutral_soft")
            status_item.setForeground(QColor(color))
            status_item.setBackground(QColor(bg))
            self.table.setItem(i, 4, status_item)

            # Last login — "YYYY-MM-DD HH:MM:SS" → "YYYY-MM-DD HH:MM"
            last_login = user.last_login or "—"
            if last_login != "—" and len(last_login) >= 16:
                last_login = last_login[:16]
            self.table.setItem(i, 5, QTableWidgetItem(last_login))

        self._update_action_buttons()

    def _format_role(self, role: str) -> str:
        """Show both languages: 'المدير · Manager' in AR mode, the reverse
        in EN mode. Uses the role.* translation keys we already have."""
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

        # Toggle button: enabled only when the action is actually allowed.
        toggle_enabled = False
        if has_selection:
            # Reset label/style to the "deactivate" default first.
            self.toggle_active_button.setText(t("users.action.deactivate"))
            make_danger(self.toggle_active_button)

            if not user.active:
                # Reactivating is always allowed.
                self.toggle_active_button.setText(t("users.action.activate"))
                make_secondary(self.toggle_active_button)
                toggle_enabled = True
            else:
                # Deactivating — block self and last-manager.
                is_self = (
                    app_state.user is not None
                    and user.user_id == app_state.user.user_id
                )
                is_last_manager = (
                    user.role == "manager"
                    and users_repo.count_active_managers() == 1
                )
                toggle_enabled = not (is_self or is_last_manager)

        self.toggle_active_button.setEnabled(toggle_enabled)

    # ---------- actions ----------

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

        # Safety: if this is the last active manager, warn the user that
        # demoting them isn't allowed — the dialog handles the enforcement,
        # but a heads-up here avoids confusing errors.
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

        # Safety 1: can't deactivate yourself
        # Safety 1: can't deactivate yourself
        if user.active and app_state.user and user.user_id == app_state.user.user_id:
            warn(
                self,
                t("users.error.self_deactivate_title"),
                t("users.error.self_deactivate_msg"),
            )
            return

        # Safety 2: can't deactivate the last active manager
        if (user.active and user.role == "manager"
                and users_repo.count_active_managers() == 1):
            warn(
                self,
                t("users.error.last_manager_title"),
                t("users.error.last_manager_deactivate_msg"),
            )
            return

        target_state = not user.active
        verb = t("users.action.activate") if target_state else t("users.action.deactivate")

        if not ask(
            self,
            t("users.confirm.title"),
            t("users.confirm.toggle_active", name=user.display_name, verb=verb),
        ):
            return

        users_repo.set_active(user.user_id, target_state)
        self.refresh()