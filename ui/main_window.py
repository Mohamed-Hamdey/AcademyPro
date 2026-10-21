"""
Main application window — v4 shell with role-gated navigation.
"""

import os
import sys
from ui.screens.championships_screen import ChampionshipsScreen
from ui.screens.dashboard_screen import DashboardScreen
from ui.screens.expenses_screen import ExpensesScreen
from qtpy.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QDialog,
)
from qtpy.QtCore import Qt, QSettings, QTimer
from qtpy.QtGui import QGuiApplication
from ui.screens.activities_screen import ActivitiesScreen
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ui.screens.scan_screen import ScanScreen
from ui.screens.player_list_screen import PlayerListScreen
from ui.screens.users_screen import UsersScreen
from ui.screens.audit_screen import AuditScreen
from ui.shell import TopBar, Sidebar, Workspace
from ui.theme import theme
from ui.i18n import t
from app_state import app as app_state
from ui.screens.recycle_bin_screen import RecycleBinScreen

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

        self._restore_geometry()

        self._pages_by_nav_key = {}
        self._nav_keys_in_order = []

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.topbar = TopBar(
            on_logout=self._on_logout,
            on_toggle_sidebar=self._toggle_sidebar,
            on_backup=self._on_backup_now,
            on_restore=self._on_restore_backup,
            on_about=self._on_about,
        )
        outer.addWidget(self.topbar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.workspace = Workspace()

        self._register_page("nav.check_in",       "checkin.title",   ScanScreen(self),        "checkin")
        self._register_page("nav.manage_players", "players.title",   PlayerListScreen(self),  "players.view")
        self._register_page("nav.dashboard",      "dash.title",      DashboardScreen(self),   "financials.view")
        self._register_page("nav.activities", "activities.title", ActivitiesScreen(self), "activities.manage")
        self._register_page("nav.users",          "users.title",   UsersScreen(self),     "users.manage")
        self._register_page("nav.expenses", "expenses.title", ExpensesScreen(self), "expenses.manage")
        self._register_page("nav.championships", "champ.title", ChampionshipsScreen(self), "championships.manage")
        self._register_page("nav.audit",          "audit.title",   AuditScreen(self),     "audit.view")

        
        # Register Recycle Bin without adding to main sidebar
        self._register_page("nav.recycle_bin",    "recycle.title", RecycleBinScreen(self),"settings.manage", hide_from_sidebar=True)

        # Signals
        self.sidebar.on_change(self._on_nav_changed)
        
        footer_idx = self.sidebar.add_footer_item("nav.recycle_bin", "🗑", required_permission="settings.manage")
        if footer_idx >= 0:
            self.sidebar.on_footer_change(self._on_footer_nav_changed)
            
        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.workspace, stretch=1)
        outer.addWidget(body, stretch=1)

        self.setCentralWidget(central)

        if self._nav_keys_in_order:
            self.sidebar.set_current_row(0)

        theme().on_change(lambda _m: self._restyle())

        QTimer.singleShot(2000, self._warm_heavy_imports)

    def _warm_heavy_imports(self):
        import threading
        def _warm():
            try:
                import cv2
                from pyzbar import pyzbar
            except Exception:
                pass
        threading.Thread(target=_warm, daemon=True).start()

    def _register_page(self, nav_key: str, title_key: str, page: QWidget,
                       permission: str, hide_from_sidebar: bool = False):
        if permission is not None and not app_state.can(permission):
            page.setParent(None)
            page.deleteLater()
            return

        if not hide_from_sidebar:
            glyph = self._glyph_for(nav_key)
            sidebar_index = self.sidebar.add_item(
                nav_key, glyph, required_permission=permission
            )
            if sidebar_index < 0:
                page.setParent(None)
                page.deleteLater()
                return

        self.workspace.add_page(nav_key, t(title_key), page)
        self._pages_by_nav_key[nav_key] = page
        self._nav_keys_in_order.append(nav_key)

    @staticmethod
    def _glyph_for(nav_key: str) -> str:
        # Returns an *icon key* understood by ui.shell._make_nav_icon().
        # These are drawn with QPainter at runtime (no external assets,
        # PyInstaller safe), and tinted from the active theme tokens.
        return {
            "nav.check_in":       "play",
            "nav.dashboard":      "chart",
            "nav.manage_players": "list",
            "nav.users":          "users",
            "nav.activities":     "running",
            "nav.expenses":       "wallet",
            "nav.audit":          "notebook",
            "nav.championships":  "trophy",
            "nav.recycle_bin":    "trash",
        }.get(nav_key, "dot")
        
        
    def _on_nav_changed(self, index: int):
        """Sidebar index → workspace page key."""
        if index < 0 or index >= len(self._nav_keys_in_order):
            return
            
        # Clear footer selection so it doesn't stay highlighted
        self.sidebar.footer_list.blockSignals(True)
        self.sidebar.footer_list.setCurrentRow(-1)
        self.sidebar.footer_list.blockSignals(False)

        nav_key = self._nav_keys_in_order[index]
        self.workspace.set_header_action(None)
        self.workspace.show_page_by_key(nav_key)

    def _on_footer_nav_changed(self, index: int):
        if index < 0:
            return
            
        # Clear main nav selection
        self.sidebar.nav_list.blockSignals(True)
        self.sidebar.nav_list.setCurrentRow(-1)
        self.sidebar.nav_list.blockSignals(False)

        self.workspace.set_header_action(None)
        self.workspace.show_page_by_key("nav.recycle_bin")
        self.workspace.set_title(t("recycle.title"))

    def _on_backup_now(self):
        from services import backup_service
        from ui.message_box import info, error
        path = backup_service.create_backup(label="manual")
        if path:
            info(self, t("backup.now.done_title"), t("backup.now.done_msg", name=os.path.basename(path)))
        else:
            error(self, t("backup.now.failed_title"), t("backup.now.failed_msg"))

    def _on_restore_backup(self):
        from ui.dialogs.restore_backup_dialog import RestoreBackupDialog
        dlg = RestoreBackupDialog(parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            from qtpy.QtWidgets import QApplication
            QApplication.instance().quit()
        
    def _on_about(self):
        from ui.dialogs.about_dialog import AboutDialog
        AboutDialog(parent=self).exec()

    def _toggle_sidebar(self):
        self.sidebar.toggle_collapsed()

    def _restyle(self):
        pass

    def _on_logout(self):
        from qtpy.QtWidgets import QApplication
        try:
            user = app_state.user
            if user is not None:
                from services import audit_service
                audit_service.auth_logout(user.username)
        except Exception:
            pass

        app_state.clear()
        self.close()

        from ui.screens.login_screen import LoginDialog
        if LoginDialog().exec() != QDialog.DialogCode.Accepted:
            QApplication.instance().quit()
            return

        global _current_window
        new_window = MainWindow()
        _current_window = new_window
        new_window.show()

    def _switch_language(self):
        from qtpy.QtWidgets import QApplication
        from qtpy.QtCore import QSettings
        from ui import i18n

        new_lang = "en" if i18n.current_language() == "ar" else "ar"
        i18n.load(new_lang)
        QSettings("MembershipSystem", "app").setValue("language", new_lang)

        app = QApplication.instance()
        if app is not None:
            app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight)

        self.close()
        global _current_window
        new_window = MainWindow()
        _current_window = new_window
        new_window.show()

    def closeEvent(self, event):
        try:
            scan = self._pages_by_nav_key.get("nav.check_in")
            if scan is not None and hasattr(scan, "stop_camera"):
                scan.stop_camera()
        except Exception:
            pass
        try:
            self._save_geometry()
        except Exception:
            pass
        super().closeEvent(event)

    _GEOM_ORG = "MembershipSystem"
    _GEOM_APP = "app"
    _GEOM_KEY = "window/geometry"

    def _save_geometry(self):
        s = QSettings(self._GEOM_ORG, self._GEOM_APP)
        s.setValue(self._GEOM_KEY, self.saveGeometry())
        s.sync()

    def _restore_geometry(self):
        s = QSettings(self._GEOM_ORG, self._GEOM_APP)
        blob = s.value(self._GEOM_KEY, None)
        if blob is None:
            return
        try:
            if not self.restoreGeometry(blob):
                return
            geo = self.frameGeometry()
            for screen in QGuiApplication.screens():
                if screen.availableGeometry().intersects(geo):
                    return
            self.resize(1100, 720)
            primary = QGuiApplication.primaryScreen()
            if primary is not None:
                avail = primary.availableGeometry()
                x = avail.x() + (avail.width() - 1100) // 2
                y = avail.y() + (avail.height() - 720) // 2
                self.move(x, y)
        except Exception:
            pass