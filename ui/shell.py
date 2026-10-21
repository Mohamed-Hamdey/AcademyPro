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

from qtpy.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QStackedWidget, QMenu,
)
from qtpy.QtCore import Qt, QSize
from qtpy.QtGui import QPixmap, QAction
from ui.user_menu import UserMenuButton

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import get_academy_name, get_academy_logo, load_config
from ui import i18n
from ui.i18n import t
from ui.theme import theme, theme_toggle_button, language_toggle_button
from ui.design import SHELL, SPACING, RADIUS
from app_state import app as app_state
from ui.language_switch import LanguageSwitch


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

    def __init__(self, on_logout=None, on_toggle_sidebar=None,
                 on_backup=None, on_restore=None, on_about=None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(SHELL["topbar_height"])
        self._on_logout = on_logout
        self._on_toggle_sidebar = on_toggle_sidebar
        self._on_backup = on_backup
        self._on_restore = on_restore
        self._on_about = on_about
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



        # ---- User menu button (replaces the old QPushButton + QMenu) ----
        self.user_menu = UserMenuButton(parent=self)
        self._populate_user_menu()
        layout.addWidget(self.user_menu)

        # ---- Language + theme toggles ----
        self.language_button = LanguageSwitch()
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

    def _on_search_submit(self):
        """Called when the user presses Enter in the global search box."""
        if self._on_search is None:
            return
        query = self.search_input.text().strip()
        if not query:
            return
        self._on_search(query)
    def _populate_user_menu(self):
        user = app_state.user
        if user is not None:
            role_label = t(f"role.{user.role}")
            self.user_menu.set_user(user.display_name, role_label)

            self.user_menu.add_item(
                t("menu.change_password"),
                self._on_change_password,
                icon="🔑",
            )

            if app_state.can("settings.manage"):
                self.user_menu.add_separator()
                self.user_menu.add_item(
                    t("menu.backup_now"),
                    self._on_backup_now_clicked,
                    icon="💾",
                )
                self.user_menu.add_item(
                    t("menu.restore_backup"),
                    self._on_restore_backup_clicked,
                    icon="📥",
                )

            self.user_menu.add_separator()
            self.user_menu.add_item(
                t("menu.about"),
                self._on_about_clicked,
                icon="ℹ️",
            )

            self.user_menu.add_separator()
            self.user_menu.add_item(
                t("menu.logout"),
                self._on_logout_clicked,
                icon="🚪",
                danger=True,
            )
        else:
            self.user_menu.set_user(t("menu.not_signed_in"), "")
    def _on_backup_now_clicked(self):
        if self._on_backup is not None:
            self._on_backup()

    def _on_restore_backup_clicked(self):
        if self._on_restore is not None:
            self._on_restore()
            
    def _on_about_clicked(self):
        if self._on_about is not None:
            self._on_about()
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

        # Footer area for items pinned to the bottom (recycle bin, etc.)
        self.footer_list = QListWidget()
        self.footer_list.setObjectName("navList") # reuse styles
        self.footer_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.footer_list.setFixedHeight(60) # enough for one item
        layout.addWidget(self.footer_list)

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
        for i in range(self.nav_list.count()):
            self._render_item(i)
        for i in range(self.footer_list.count()):
            self._render_footer_item(i)
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
    def add_footer_item(self, label_key: str, icon_glyph: str,
                        required_permission: str = None) -> int:
        """Add a nav item pinned to the bottom of the sidebar."""
        if required_permission is not None:
            if not app_state.can(required_permission):
                return -1

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, (label_key, icon_glyph))
        item.setSizeHint(QSize(0, 42))
        self.footer_list.addItem(item)
        self._render_footer_item(self.footer_list.count() - 1)
        return self.footer_list.count() - 1

    def _render_footer_item(self, index: int):
        item = self.footer_list.item(index)
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

    def set_footer_current_row(self, index: int):
        self.footer_list.setCurrentRow(index)
        # Clear selection from main list to avoid double-selection look
        self.nav_list.clearSelection()

    def on_footer_change(self, callback):
        self.footer_list.currentRowChanged.connect(callback)
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

        # Slot for a per-page header action (e.g. a Back button on
        # screens that push their own sub-page). Empty by default.
        self.header_action_slot = QHBoxLayout()
        self.header_action_slot.setSpacing(8)
        header.addLayout(self.header_action_slot)

        self._header_action_widget = None

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

    def set_header_action(self, widget: QWidget = None):
        # Remove the previous action from the header without deleting it.
        previous = self._header_action_widget

        if previous is not None:
            self.header_action_slot.removeWidget(previous)
            previous.hide()
            previous.setParent(None)
            self._header_action_widget = None

        if widget is None:
            return

        # Detach from any existing layout before adding it to this header.
        parent = widget.parentWidget()
        if parent is not None:
            layout = parent.layout()
            if layout is not None:
                layout.removeWidget(widget)

        widget.hide()
        widget.setParent(self)
        self.header_action_slot.addWidget(widget)
        self._header_action_widget = widget
        widget.show()

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