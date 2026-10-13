"""
Main application window — v4 shell with role-gated navigation.

Sidebar items are permission-gated via app_state.app.can(...). A user
menu in the top bar shows the current user and offers Logout.

Logout tears down the window and returns to the login dialog. The user
stays logged out until they authenticate again.
"""

import os
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QDialog,
)
from PyQt6.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ui.screens.scan_screen import ScanScreen
from ui.screens.player_list_screen import PlayerListScreen
from ui.screens.users_screen import UsersScreen
from ui.screens.audit_screen import AuditScreen
from ui.shell import TopBar, Sidebar, Workspace
from ui.theme import theme
from ui.i18n import t
from app_state import app as app_state


_current_window: "MainWindow" = None


def request_language_change():
    if _current_window is None:
        return
    _current_window._switch_language()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        global _current_window
        _current_window = self

        self.setWindowTitle(t("app.window_title"))
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        # Map of nav_key -> page widget, only for pages the user can see.
        self._pages_by_nav_key = {}
        # Ordered list of nav keys the user actually sees, for sidebar dispatch.
        self._nav_keys_in_order = []

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- Top bar (with logout callback) ----
        self.topbar = TopBar(on_logout=self._on_logout)
        outer.addWidget(self.topbar)

        # ---- Body: sidebar + workspace ----
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.workspace = Workspace()

        # Register pages (only those the user has permission for).
        # Order here determines sidebar order.
        self._register_page("nav.check_in",       "checkin.title", ScanScreen(),       "checkin")
        self._register_page("nav.manage_players", "players.title", PlayerListScreen(), "players.view")
        self._register_page("nav.users",          "users.title",   UsersScreen(),     "users.manage")
        self._register_page("nav.audit",          "audit.title",   AuditScreen(),     "audit.view")

        # One signal drives everything.
        self.sidebar.on_change(self._on_nav_changed)

        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.workspace, stretch=1)
        outer.addWidget(body, stretch=1)

        self.setCentralWidget(central)

        # Select the first visible nav item
        if self._nav_keys_in_order:
            self.sidebar.set_current_row(0)

        theme().on_change(lambda _m: self._restyle())

    def _register_page(self, nav_key: str, title_key: str, page: QWidget,
                       permission: str):
        """
        Add a page to the workspace and (if permitted) a nav item to the
        sidebar. Keeps both lists in lockstep, so sidebar index == workspace
        index always holds among *visible* items.
        """
        glyph = self._glyph_for(nav_key)
        sidebar_index = self.sidebar.add_item(
            nav_key, glyph, required_permission=permission
        )

        if sidebar_index < 0:
            # Permission denied — don't register the page at all
            return

        self.workspace.add_page(nav_key, t(title_key), page)
        self._pages_by_nav_key[nav_key] = page
        self._nav_keys_in_order.append(nav_key)

    @staticmethod
    def _glyph_for(nav_key: str) -> str:
        return {
            "nav.check_in":       "▶",
            "nav.manage_players": "▤",
            "nav.users":          "👥",
            "nav.audit":          "🗒",
        }.get(nav_key, "•")

    def _on_nav_changed(self, index: int):
        """Sidebar index → workspace page key."""
        if index < 0 or index >= len(self._nav_keys_in_order):
            return
        nav_key = self._nav_keys_in_order[index]
        self.workspace.show_page_by_key(nav_key)

    def _restyle(self):
        pass

    # ---------- logout ----------

    def _on_logout(self):
        """Clear the session and return to the login dialog."""
        from PyQt6.QtWidgets import QApplication

        app_state.clear()
        self.close()

        from ui.screens.login_screen import LoginDialog
        login = LoginDialog()
        if login.exec() != QDialog.DialogCode.Accepted:
            QApplication.instance().quit()
            return

        global _current_window
        new_window = MainWindow()
        _current_window = new_window
        new_window.show()

    # ---------- language switch ----------

    def _switch_language(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QSettings
        from ui import i18n

        current = i18n.current_language()
        new_lang = "en" if current == "ar" else "ar"
        i18n.load(new_lang)
        QSettings("MembershipSystem", "app").setValue("language", new_lang)

        app = QApplication.instance()
        if app is not None:
            if i18n.is_rtl():
                app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            else:
                app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.close()
        global _current_window
        new_window = MainWindow()
        _current_window = new_window
        new_window.show()

    # ---------- lifecycle ----------

    def closeEvent(self, event):
        try:
            scan = self._pages_by_nav_key.get("nav.check_in")
            if scan is not None and hasattr(scan, "stop_camera"):
                scan.stop_camera()
        except Exception:
            pass
        super().closeEvent(event)