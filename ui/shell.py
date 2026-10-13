"""
Shell widgets — the reusable chrome that wraps every screen.

Layout (RTL: sidebar on the right):
    ┌────────────────────────────────────────────┐
    │  [TopBar: logo · search · user · toggle]   │
    ├──────────────┬─────────────────────────────┤
    │              │                             │
    │   Sidebar    │        Workspace            │
    │              │                             │
    └──────────────┴─────────────────────────────┘
"""

import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QStackedWidget, QMenu,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QAction

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import get_academy_name, get_academy_logo, load_config
from ui import i18n
from ui.i18n import t
from ui.theme import theme, theme_toggle_button, language_toggle_button
from ui.design import SHELL, SPACING, RADIUS
from app_state import app as app_state


# ---------------------------------------------------------------------------
# TopBar
# ---------------------------------------------------------------------------

class TopBar(QWidget):
    """
    Top navigation bar with:
      * Academy logo + name
      * Global search
      * User menu (current user + logout)
      * Language toggle
      * Theme toggle
    """

    def __init__(self, on_logout=None, on_toggle_sidebar=None, parent=None):
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(SHELL["topbar_height"])
        self._on_logout = on_logout
        self._on_toggle_sidebar = on_toggle_sidebar
        self._build_ui()
        theme().on_change(lambda _m: self.restyle())
        self.restyle()
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # ---- Logo + name (clickable → toggles the sidebar) ----
        self.brand_widget = QWidget()
        self.brand_widget.setObjectName("brandWidget")
        self.brand_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self.brand_widget.setToolTip(t("sidebar.toggle_hint"))
        self.brand_widget.mousePressEvent = self._on_brand_clicked

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(32, 32)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_logo()

        self.title_label = QLabel()
        self.title_label.setObjectName("topBarTitle")

        brand_row = QHBoxLayout(self.brand_widget)
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(10)
        brand_row.addWidget(self.logo_label)
        brand_row.addWidget(self.title_label)
        brand_row.addStretch()

        layout.addWidget(self.brand_widget, stretch=1)

        # ---- Global search ----
        self.search_input = QLineEdit()
        self.search_input.setObjectName("globalSearch")
        self.search_input.setPlaceholderText(t("shell.search_placeholder"))
        layout.addWidget(self.search_input)

        # ---- User menu button ----
        self.user_button = QPushButton()
        self.user_button.setObjectName("userMenuButton")
        self.user_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.user_button.clicked.connect(self._show_user_menu)
        layout.addWidget(self.user_button)

        # ---- Language + theme toggles ----
        self.language_button = language_toggle_button()
        self.theme_button = theme_toggle_button()
        layout.addWidget(self.language_button)
        layout.addWidget(self.theme_button)

    def _load_logo(self):
        path = get_academy_logo()
        if path:
            pix = QPixmap(path).scaled(
                32, 32,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(pix)
        else:
            initials = "".join(w[0] for w in get_academy_name().split()[:3]).upper()
            self.logo_label.setText(initials or "A")
    def _on_brand_clicked(self, event):
        if self._on_toggle_sidebar is not None:
            self._on_toggle_sidebar()
    def _show_user_menu(self):
        menu = QMenu(self)

        # Header — the current user's display name + role
        user = app_state.user
        if user is not None:
            header = QAction(f"👤  {user.display_name}", self)
            header.setEnabled(False)
            menu.addAction(header)

            role_label = t(f"role.{user.role}")
            role_action = QAction(f"    {role_label}", self)
            role_action.setEnabled(False)
            menu.addAction(role_action)
        else:
            header = QAction(t("menu.not_signed_in"), self)
            header.setEnabled(False)
            menu.addAction(header)

        menu.addSeparator()

        # Change password (if logged in)
        if user is not None:
            change_pw = QAction(t("menu.change_password"), self)
            change_pw.triggered.connect(self._on_change_password)
            menu.addAction(change_pw)

        # Logout
        logout = QAction(t("menu.logout"), self)
        logout.triggered.connect(self._on_logout_clicked)
        menu.addAction(logout)

        # Show the menu anchored to the button
        menu.exec(self.user_button.mapToGlobal(self.user_button.rect().bottomLeft()))

    def _on_change_password(self):
        user = app_state.user
        if user is None:
            return
        from ui.screens.change_password_dialog import ChangePasswordDialog
        dlg = ChangePasswordDialog(user, force=False, parent=self)
        dlg.exec()

    def _on_logout_clicked(self):
        if self._on_logout is not None:
            self._on_logout()

    def restyle(self):
        tm = theme()

        # Top bar background + border
        self.setStyleSheet(
            f"QWidget#topBar {{"
            f"  background-color: {tm.color('topbar_bg')};"
            f"  border-bottom: 1px solid {tm.color('topbar_border')};"
            f"}}"
        )

        # Title label
        cfg = load_config()
        if i18n.current_language() == "ar":
            name = cfg.get("academy_name_ar") or cfg.get("academy_name", "")
        else:
            name = cfg.get("academy_name", "")
        self.title_label.setText(name)
        self.title_label.setStyleSheet(
            f"QLabel#topBarTitle {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 15px;"
            f"  font-weight: 600;"
            f"}}"
        )

        # Logo monogram background (if no image)
        if self.logo_label.pixmap() is None or self.logo_label.pixmap().isNull():
            self.logo_label.setStyleSheet(
                f"QLabel {{"
                f"  background-color: {tm.color('primary')};"
                f"  color: {tm.color('text_on_primary')};"
                f"  font-size: 13px; font-weight: 700;"
                f"  border-radius: {RADIUS['sm']}px;"
                f"}}"
            )

        # User menu button — style it as a quiet pill
        # User menu button — style it as a quiet pill with an avatar
        user = app_state.user
        if user is not None:
            self.user_button.setText(f"   {user.display_name}  ▾")
            # Attach the user's avatar as an icon (photo or initial)
            try:
                from ui.screens.users_screen import _avatar_pixmap
                from PyQt6.QtGui import QIcon
                self.user_button.setIcon(QIcon(_avatar_pixmap(user)))
                self.user_button.setIconSize(self.user_button.iconSize())
            except Exception:
                self.user_button.setIcon(QIcon())
        else:
            self.user_button.setText(t("menu.not_signed_in"))

        self.user_button.setStyleSheet(
            f"QPushButton#userMenuButton {{"
            f"  background-color: transparent;"
            f"  color: {tm.color('text')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['md']}px;"
            f"  padding: 6px 12px;"
            f"  font-weight: 500;"
            f"  font-size: 13px;"
            f"}}"
            f"QPushButton#userMenuButton:hover {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"}}"
        )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

class Sidebar(QWidget):
    """
    Navigation rail. Items are permission-gated: if the current user's
    role isn't allowed the item's `required_permission`, the item is not
    added at all.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(SHELL["sidebar_width"])
        self._collapsed = False
        self._nav_entries = []   # list of (label_key, glyph) in order
        self._build_ui()
        theme().on_change(lambda _m: self.restyle())
        self.restyle()
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        self.nav_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.nav_list, stretch=1)

    def add_item(self, label_key: str, icon_glyph: str,
                 required_permission: str = None) -> int:
        """
        Add a nav item. See the class docstring for permission behavior.
        """
        if required_permission is not None:
            if not app_state.can(required_permission):
                return -1

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, (label_key, icon_glyph))
        item.setSizeHint(QSize(0, 42))
        self.nav_list.addItem(item)
        self._nav_entries.append((label_key, icon_glyph))
        self._render_item(self.nav_list.count() - 1)
        return self.nav_list.count() - 1

    def _render_item(self, index: int):
        """Render one nav item according to the current collapse state."""
        item = self.nav_list.item(index)
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        label_key, glyph = data
        if self._collapsed:
            item.setText(glyph)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip(t(label_key))
            item.setSizeHint(QSize(0, 48))
        else:
            item.setText(f"  {glyph}   {t(label_key)}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item.setToolTip("")
            item.setSizeHint(QSize(0, 42))

    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.setFixedWidth(SHELL["sidebar_collapsed_width"])
        else:
            self.setFixedWidth(SHELL["sidebar_width"])
        # Re-render every item to switch glyph-only / label view
        for i in range(self.nav_list.count()):
            self._render_item(i)
        self.restyle()

    def collapse(self):
        if not self._collapsed:
            self.toggle_collapsed()

    def expand(self):
        if self._collapsed:
            self.toggle_collapsed()

    def current_row(self) -> int:
        return self.nav_list.currentRow()

    def set_current_row(self, index: int):
        self.nav_list.setCurrentRow(index)

    def on_change(self, callback):
        self.nav_list.currentRowChanged.connect(callback)

    def restyle(self):
        pass


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

class Workspace(QWidget):
    """
    Content area. Holds a page header (title + optional action) and the
    current page widget below.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workspace")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()
        theme().on_change(lambda _m: self.restyle())
        self.restyle()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SHELL["content_gutter"],
            SHELL["content_gutter"],
            SHELL["content_gutter"],
            SHELL["content_gutter"],
        )
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.title_label = QLabel()
        header.addWidget(self.title_label)
        header.addStretch()
        layout.addLayout(header)

        self.pages = QStackedWidget()
        layout.addWidget(self.pages, stretch=1)

    def add_page(self, key: str, title_text: str, widget: QWidget):
        if not hasattr(self, "_page_keys"):
            self._page_keys = {}
        self.pages.addWidget(widget)
        self._page_keys[key] = (widget, title_text)

    def show_page_by_index(self, index: int):
        self.pages.setCurrentIndex(index)
        widget = self.pages.widget(index)
        self._update_title_for_widget(widget)

    def show_page_by_key(self, key: str):
        if not hasattr(self, "_page_keys") or key not in self._page_keys:
            return
        widget, _ = self._page_keys[key]
        index = self.pages.indexOf(widget)
        if index >= 0:
            self.pages.setCurrentIndex(index)
            self._update_title_for_widget(widget)

    def _update_title_for_widget(self, widget: QWidget):
        if widget is None or not hasattr(self, "_page_keys"):
            self.set_title("")
            return
        for _, (w, title) in self._page_keys.items():
            if w is widget:
                self.set_title(title)
                return
        self.set_title("")

    def set_title(self, title: str):
        self.title_label.setText(title)

    def restyle(self):
        # Only the title label needs inline styling. The workspace
        # background comes from the global QSS (QWidget#workspace rule).
        tm = theme()
        self.title_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 22px;"
            f"  font-weight: 700;"
            f"}}"
        )