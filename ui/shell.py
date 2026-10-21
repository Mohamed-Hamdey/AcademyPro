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
            self.user_menu.set_user(user.display_name, role_label, user.photo_path)
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


from qtpy.QtCore import QPointF,QRectF
from qtpy.QtGui import QColor, QPainter,QPen, QIcon,QPainterPath,QPixmap


def _make_nav_icon(kind: str, color: str, size: int = 20) -> QIcon:
    """
    Draw a monochrome outline icon with QPainter and return it as a QIcon.

    No external assets, no font dependency. PyInstaller safe. The icon
    color is passed in, so it can be re-tinted on every theme change.

    Supported kinds:
        play, chart, list, users, running, wallet, notebook, trophy,
        trash, dot
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(
            QColor(color), 1.8,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        w = float(size)
        # We work in a 20x20 unit space, then scale by size/20 so
        # every path is easy to reason about.
        s = w / 20.0

        def p(x, y):
            return QPointF(x * s, y * s)

        if kind == "play":
            # Filled triangle pointing right
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            path = QPainterPath()
            path.moveTo(p(7, 5))
            path.lineTo(p(15, 10))
            path.lineTo(p(7, 15))
            path.closeSubpath()
            painter.drawPath(path)

        elif kind == "chart":
            # 3 bars of increasing height
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            for x, h in ((4, 6), (9, 10), (14, 14)):
                painter.drawRoundedRect(
                    QRectF(x * s, (18 - h) * s, 2.5 * s, h * s), 0.8 * s, 0.8 * s
                )

        elif kind == "list":
            # 3 horizontal lines with a bullet dot on the left
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            for y in (6, 10, 14):
                painter.drawEllipse(p(4.5, y), 1.0 * s, 1.0 * s)
            painter.setPen(QPen(QColor(color), 1.8,
                                Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            for y in (6, 10, 14):
                painter.drawLine(p(8, y), p(16, y))

        elif kind == "users":
            # Two overlapping person silhouettes
            painter.setPen(QPen(QColor(color), 1.6,
                                Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Back person (smaller, offset)
            painter.drawEllipse(p(9.5, 5.5), 2.2 * s, 2.2 * s)
            painter.drawArc(
                QRectF(6.5 * s, 10 * s, 8 * s, 8 * s), 0, 180 * 16
            )
            # Front person
            painter.drawEllipse(p(13.0, 6.5), 2.2 * s, 2.2 * s)
            painter.drawArc(
                QRectF(10 * s, 11 * s, 8 * s, 8 * s), 0, 180 * 16
            )

        elif kind == "running":
            # A simple running figure: head + angled body + two legs
            painter.setPen(QPen(QColor(color), 1.8,
                                Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(p(12.5, 4.2), 1.6 * s, 1.6 * s)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(color), 1.8,
                                Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            # Body
            painter.drawLine(p(11.5, 6.2), p(8.5, 11.0))
            # Arms
            painter.drawLine(p(10.5, 8.0), p(6.5, 8.0))
            painter.drawLine(p(10.5, 8.0), p(13.5, 9.5))
            # Legs
            painter.drawLine(p(8.5, 11.0), p(6.0, 15.5))
            painter.drawLine(p(8.5, 11.0), p(12.5, 15.5))

        elif kind == "wallet":
            # Rounded rectangle + coin slot
            painter.drawRoundedRect(
                QRectF(3 * s, 6 * s, 14 * s, 10 * s), 2 * s, 2 * s
            )
            # Flap on top
            painter.drawLine(p(3, 6), p(14, 6))
            painter.drawLine(p(14, 6), p(17, 3))
            painter.drawLine(p(17, 3), p(3, 3))
            # Coin
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(p(14.0, 11.0), 1.4 * s, 1.4 * s)

        elif kind == "notebook":
            # Notebook with binding rings on the left
            painter.drawRoundedRect(
                QRectF(5 * s, 3 * s, 11 * s, 14 * s), 1.5 * s, 1.5 * s
            )
            painter.setPen(QPen(QColor(color), 1.5,
                                Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            for y in (5.5, 8.5, 11.5, 14.5):
                painter.drawLine(p(3.5, y), p(6.5, y))

        elif kind == "trophy":
            # Cup + handles + base
            painter.drawRoundedRect(
                QRectF(6 * s, 3 * s, 8 * s, 8 * s), 1.2 * s, 1.2 * s
            )
            # Handles
            painter.drawArc(
                QRectF(3 * s, 4.5 * s, 4 * s, 5 * s), 90 * 16, 180 * 16
            )
            painter.drawArc(
                QRectF(13 * s, 4.5 * s, 4 * s, 5 * s), 270 * 16, 180 * 16
            )
            # Stem + base
            painter.drawLine(p(10, 11), p(10, 14))
            painter.drawLine(p(7, 16.5), p(13, 16.5))
            painter.drawLine(p(10, 14), p(10, 16.5))

        elif kind == "trash":
            # Can + lid + handle + 2 lines
            painter.drawRoundedRect(
                QRectF(5 * s, 6 * s, 10 * s, 11 * s), 1.5 * s, 1.5 * s
            )
            painter.drawLine(p(4, 6), p(16, 6))
            painter.drawLine(p(8, 3.5), p(12, 3.5))
            painter.drawLine(p(8, 6), p(8, 3.5))
            painter.drawLine(p(12, 6), p(12, 3.5))
            painter.setPen(QPen(QColor(color), 1.4,
                                Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.drawLine(p(8.5, 9.5), p(8.5, 14.0))
            painter.drawLine(p(11.5, 9.5), p(11.5, 14.0))

        else:  # "dot" fallback
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(p(10, 10), 2 * s, 2 * s)

    finally:
        painter.end()

    return QIcon(pix)


class Sidebar(QWidget):
    """
    Navigation rail. Items are permission-gated: if the current user's
    role isn't allowed the item's `required_permission`, the item is not
    added at all.

    Items store a semantic icon key (e.g. "users", "trophy") in
    ItemDataRole.UserRole, not an emoji. The key is turned into a QIcon
    by _make_nav_icon() in both collapsed and expanded states, which is
    why the collapsed view never shows "..." anymore.
    """

    _ICON_SIZE = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(SHELL["sidebar_width"])
        self._collapsed = False
        self._nav_entries = []   # list of (label_key, icon_key)
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
        self.nav_list.setIconSize(QSize(self._ICON_SIZE, self._ICON_SIZE))
        # Prevent Qt from ever eliding our text/icon to "...".
        self.nav_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        layout.addWidget(self.nav_list, stretch=1)

        self.footer_list = QListWidget()
        self.footer_list.setObjectName("navList")
        self.footer_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.footer_list.setIconSize(QSize(self._ICON_SIZE, self._ICON_SIZE))
        self.footer_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.footer_list.setFixedHeight(60)
        layout.addWidget(self.footer_list)

    # ---------- public API ----------

    def add_item(self, label_key: str, icon_key: str,
                 required_permission: str = None) -> int:
        if required_permission is not None:
            if not app_state.can(required_permission):
                return -1

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, (label_key, icon_key))
        item.setSizeHint(QSize(0, 42))
        self.nav_list.addItem(item)
        self._nav_entries.append((label_key, icon_key))
        self._render_item(self.nav_list.count() - 1)
        return self.nav_list.count() - 1

    def add_footer_item(self, label_key: str, icon_key: str,
                        required_permission: str = None) -> int:
        if required_permission is not None:
            if not app_state.can(required_permission):
                return -1

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, (label_key, icon_key))
        item.setSizeHint(QSize(0, 42))
        self.footer_list.addItem(item)
        self._render_footer_item(self.footer_list.count() - 1)
        return self.footer_list.count() - 1

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self.setFixedWidth(
            SHELL["sidebar_collapsed_width"] if self._collapsed
            else SHELL["sidebar_width"]
        )
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

    def is_collapsed(self) -> bool:
        return self._collapsed

    def current_row(self) -> int:
        return self.nav_list.currentRow()

    def set_current_row(self, index: int):
        self.nav_list.setCurrentRow(index)

    def on_change(self, callback):
        self.nav_list.currentRowChanged.connect(callback)

    def set_footer_current_row(self, index: int):
        self.footer_list.setCurrentRow(index)
        self.nav_list.clearSelection()

    def on_footer_change(self, callback):
        self.footer_list.currentRowChanged.connect(callback)

    # ---------- rendering ----------

    def _render_item(self, index: int):
        item = self.nav_list.item(index)
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        label_key, icon_key = data
        self._apply_item_state(item, label_key, icon_key)

    def _render_footer_item(self, index: int):
        item = self.footer_list.item(index)
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        label_key, icon_key = data
        self._apply_item_state(item, label_key, icon_key)

    def _apply_item_state(self, item: QListWidgetItem,
                          label_key: str, icon_key: str):
        selected = item.isSelected()
        color = (
            theme().color("nav_item_sel_text") if selected
            else theme().color("nav_item")
        )
        icon = _make_nav_icon(icon_key, color, self._ICON_SIZE)

        if self._collapsed:
            # Icon only — no text at all. Centered. Tooltip still shows
            # the label on hover so the user can identify the section.
            item.setIcon(icon)
            item.setText("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip(t(label_key))
            item.setSizeHint(QSize(0, 48))
        else:
            item.setIcon(icon)
            item.setText("  " + t(label_key))
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            item.setToolTip("")
            item.setSizeHint(QSize(0, 42))

    def restyle(self):
        """Re-tint every icon to the current theme's nav colors."""
        for i in range(self.nav_list.count()):
            self._render_item(i)
        for i in range(self.footer_list.count()):
            self._render_footer_item(i)

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