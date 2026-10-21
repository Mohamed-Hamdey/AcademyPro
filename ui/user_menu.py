"""
UserMenuButton — top-bar user widget with a custom popup card.

Save as ui/user_menu.py and use it in place of the QMenu-based user button
in ui/shell.py (TopBar):

    from ui.user_menu import UserMenuButton

    self.user_menu = UserMenuButton(user.username, role_label)     # role_label = e.g. t("role.manager")
    self.user_menu.add_item(t("menu.change_password"), self._on_change_password, icon="🔑")
    self.user_menu.add_separator()
    self.user_menu.add_item(t("menu.backup_now"), self._on_backup, icon="💾")
    self.user_menu.add_item(t("menu.restore"), self._on_restore, icon="📥")
    self.user_menu.add_separator()
    self.user_menu.add_item(t("menu.about"), self._on_about, icon="ℹ️")
    self.user_menu.add_separator()
    self.user_menu.add_item(t("menu.logout"), self._on_logout, icon="🚪", danger=True)

Keep whatever permission checks you already have (e.g. only add backup/restore
items when app_state.can(...)). Use your existing t() keys and handlers.

Design:
  * Trigger: rounded pill with a coloured initial avatar, the user's name, the
    role under it (small, muted) and a chevron that flips while open.
  * Popup: a card with a large avatar, name and a role pill, a divider, then
    icon rows. Hover/keyboard highlight; the logout row is red.
  * RTL aware (popup aligns to the trigger's start edge), keyboard friendly
    (Tab to the trigger, Space/Enter/Down opens, Up/Down moves, Enter chooses,
    Esc closes).
  * The popup window is created once, lazily, and reused — nothing is created
    per open. Chosen actions run after the popup has closed, so dialogs open
    cleanly.
"""

import time

from qtpy.QtCore import Qt, QRectF, QPointF, QPoint, QTimer
from qtpy.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QTextOption
from qtpy.QtWidgets import (
    QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy,
    QGraphicsDropShadowEffect, QApplication,
)

from ui.theme import theme, ThemedWidget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AVATAR_COLORS = ("#2563EB", "#16A34A", "#9333EA", "#EA580C", "#0D9488")


def _col(name: str, fallback_token: str, default: str) -> QColor:
    """Resolve a theme colour without ever raising."""
    try:
        pal = theme().palette()
        return QColor(pal.get(name) or pal.get(fallback_token) or default)
    except Exception:
        return QColor(default)


def _hex(name: str, fallback_token: str, default: str) -> str:
    return _col(name, fallback_token, default).name()


# ---------------------------------------------------------------------------
# Small painted widgets
# ---------------------------------------------------------------------------

class _Avatar(QWidget):
    """Circle with the user's initial; colour is derived from the name."""

    def __init__(self, size: int, parent=None):
        QWidget.__init__(self, parent)
        self._size = size
        self._text = "?"
        self._color = QColor(_AVATAR_COLORS[0])
        self.setFixedSize(size, size)

    def set_user(self, name: str):
        name = (name or "").strip()
        self._text = name[:1].upper() if name else "?"
        idx = (sum(ord(ch) for ch in name) % len(_AVATAR_COLORS)) if name else 0
        self._color = QColor(_AVATAR_COLORS[idx])
        self.update()

    def paintEvent(self, event):
        s = float(self._size)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._color))
            painter.drawEllipse(QRectF(0, 0, s, s))

            font = QFont(self.font())
            font.setPixelSize(max(10, int(s * 0.42)))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(QRectF(0, 0, s, s), self._text,
                             QTextOption(Qt.AlignmentFlag.AlignCenter))
        finally:
            painter.end()


class _Chevron(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._open = False
        self.setFixedSize(14, 14)

    def set_open(self, value: bool):
        self._open = bool(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QPen(_col("text_secondary", "text_secondary", "#64748B"), 1.7,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            if self._open:
                pts = ((3.5, 8.5), (7.0, 5.0), (10.5, 8.5))
            else:
                pts = ((3.5, 5.5), (7.0, 9.0), (10.5, 5.5))
            a, b, c = (QPointF(*pt) for pt in pts)
            painter.drawLine(a, b)
            painter.drawLine(b, c)
        finally:
            painter.end()


# ---------------------------------------------------------------------------
# Popup rows
# ---------------------------------------------------------------------------

class _Row(QFrame):
    """One clickable menu row: icon + text. Painted hover / focus highlight."""

    def __init__(self, text: str, icon: str, danger: bool, on_activate, parent=None):
        QFrame.__init__(self, parent)
        self.setObjectName("userMenuRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._danger = danger
        self._hover = False
        self._on_activate = on_activate

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(10)

        self.icon_lbl = QLabel(icon or "", self)
        self.icon_lbl.setFixedWidth(22)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_lbl = QLabel(text, self)

        lay.addWidget(self.icon_lbl)
        lay.addWidget(self.text_lbl, 1)
        self.apply_theme()

    def apply_theme(self):
        color = _hex("danger", "danger", "#DC2626") if self._danger else _hex("text", "text", "#172033")
        self.text_lbl.setStyleSheet(
            f"QLabel {{ color: {color}; font-size: 13px; font-weight: 500; background: transparent; }}"
        )
        self.icon_lbl.setStyleSheet("QLabel { font-size: 15px; background: transparent; }")
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if self.rect().contains(pos):
                self._on_activate(self._on_activate_cb)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._on_activate(self._on_activate_cb)
            event.accept()
            return
        super().keyPressEvent(event)

    # The popup hands us (chooser, callback) — see _UserPopup.set_entries().
    _on_activate_cb = None

    def paintEvent(self, event):
        if not (self._hover or self.hasFocus()):
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if self._danger:
                bg = _col("danger_soft", "surface_alt", "#FEE2E2")
            else:
                bg = _col("btn_secondary_hover", "surface_alt", "#F1F5F9")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0, 0, 0, 0), 8, 8)
        finally:
            painter.end()


# ---------------------------------------------------------------------------
# Popup card
# ---------------------------------------------------------------------------

class _UserPopup(ThemedWidget, QFrame):
    _M = 14            # transparent margin that holds the drop shadow
    _CARD_W = 264

    def __init__(self, owner):
        QFrame.__init__(
            self, owner,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self._owner = owner
        self._rows = []
        self.setObjectName("userPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(self._CARD_W + 2 * self._M)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self._M, self._M, self._M, self._M)
        outer.setSpacing(0)

        self.card = QFrame(self)
        self.card.setObjectName("userMenuCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(8, 8, 8, 8)
        card_lay.setSpacing(0)

        # ---- header: big avatar + name + role pill ----
        header = QWidget(self.card)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(10, 10, 10, 10)
        h_lay.setSpacing(12)

        self.header_avatar = _Avatar(44, header)
        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        self.name_lbl = QLabel("", header)
        self.role_lbl = QLabel("", header)
        self.role_lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        text_col.addStretch(1)
        text_col.addWidget(self.name_lbl)
        text_col.addWidget(self.role_lbl, 0, Qt.AlignmentFlag.AlignLeft)
        text_col.addStretch(1)
        h_lay.addWidget(self.header_avatar)
        h_lay.addLayout(text_col, 1)
        card_lay.addWidget(header)

        self._header_divider = self._make_divider()
        card_lay.addWidget(self._header_divider)
        card_lay.addSpacing(4)

        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(2)
        card_lay.addLayout(self.items_layout)

        self._init_theme()

    # ---------- building ----------

    def _make_divider(self) -> QFrame:
        line = QFrame(self.card)
        line.setObjectName("userMenuDivider")
        line.setFixedHeight(1)
        line.setStyleSheet(
            f"QFrame#userMenuDivider {{ background-color: {_hex('divider', 'border', '#E8EDF3')}; border: none; }}"
        )
        return line

    def set_user(self, name: str, role: str):
        self.header_avatar.set_user(name)
        self.name_lbl.setText(name or "")
        self.role_lbl.setText(role or "")
        self.role_lbl.setVisible(bool(role))

    def _clear_items(self):
        self._rows = []
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()               # hide() first: no stray top-level flashes
                w.setParent(None)
                w.deleteLater()

    def set_entries(self, entries):
        self._clear_items()
        for entry in entries:
            if entry[0] == "sep":
                self.items_layout.addSpacing(4)
                self.items_layout.addWidget(self._make_divider())
                self.items_layout.addSpacing(4)
            else:
                _, text, icon, danger, callback = entry
                row = _Row(text, icon, danger, self._owner._on_item_chosen, self.card)
                row._on_activate_cb = callback
                self.items_layout.addWidget(row)
                self._rows.append(row)
        self.restyle()

    # ---------- theme ----------

    def restyle(self):
        surface = _hex("surface", "surface", "#FFFFFF")
        border = _hex("border", "border", "#DCE3EC")
        text = _hex("text", "text", "#172033")
        primary = _hex("primary", "primary", "#2563EB")
        primary_soft = _hex("primary_soft", "primary", "#DBEAFE")

        self.card.setStyleSheet(
            f"QFrame#userMenuCard {{ background-color: {surface}; "
            f"border: 1px solid {border}; border-radius: 14px; }}"
        )
        self.name_lbl.setStyleSheet(
            f"QLabel {{ color: {text}; font-size: 15px; font-weight: 700; background: transparent; }}"
        )
        self.role_lbl.setStyleSheet(
            f"QLabel {{ color: {primary}; background-color: {primary_soft}; "
            f"border-radius: 9px; padding: 2px 10px; font-size: 11px; font-weight: 600; }}"
        )
        self._header_divider.setStyleSheet(
            f"QFrame#userMenuDivider {{ background-color: {_hex('divider', 'border', '#E8EDF3')}; border: none; }}"
        )
        for row in self._rows:
            row.apply_theme()

    # ---------- showing ----------

    def popup_below(self, button: QWidget):
        self.card.setFixedWidth(self._CARD_W)
        self.adjustSize()

        m = self._M
        top_left = button.mapToGlobal(QPoint(0, 0))
        rtl = button.layoutDirection() == Qt.LayoutDirection.RightToLeft

        y = top_left.y() + button.height() + 4 - m
        if rtl:
            x = top_left.x() + button.width() - self.width() + m
        else:
            x = top_left.x() - m

        screen = QApplication.screenAt(top_left) or QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            x = max(geo.left() + 4 - m, min(x, geo.right() - 4 - self.width() + m))

        self.move(x, y)
        self.show()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._owner._on_popup_hidden()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self._rows:
            cur = next((i for i, r in enumerate(self._rows) if r.hasFocus()), -1)
            if event.key() == Qt.Key.Key_Down:
                idx = 0 if cur < 0 else (cur + 1) % len(self._rows)
            else:
                idx = len(self._rows) - 1 if cur < 0 else (cur - 1) % len(self._rows)
            self._rows[idx].setFocus(Qt.FocusReason.TabFocusReason)
            event.accept()
            return
        super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Trigger (the widget that lives in the top bar)
# ---------------------------------------------------------------------------

class UserMenuButton(ThemedWidget, QWidget):
    """Avatar + name + role + chevron. Click to open the user popup."""

    def __init__(self, name: str = "", role: str = "", parent=None):
        QWidget.__init__(self, parent)
        self.setObjectName("userMenuButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._entries = []
        self._entries_dirty = True
        self._popup = None
        self._hover = False
        self._pressed = False
        self._open = False
        self._closed_at = 0.0
        self._name = ""
        self._role = ""

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(10)

        self.avatar = _Avatar(32, self)
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        self.name_lbl = QLabel(self)
        self.role_lbl = QLabel(self)
        text_col.addWidget(self.name_lbl)
        text_col.addWidget(self.role_lbl)
        self.chevron = _Chevron(self)

        lay.addWidget(self.avatar)
        lay.addLayout(text_col)
        lay.addWidget(self.chevron)

        self.set_user(name, role)
        self._init_theme()

    # ---------- public API ----------

    def set_user(self, name: str, role: str = ""):
        self._name = name or ""
        self._role = role or ""
        self.avatar.set_user(self._name)

        font = QFont(self.font())
        font.setPixelSize(13)
        font.setBold(True)
        shown = QFontMetrics(font).elidedText(self._name, Qt.TextElideMode.ElideRight, 140)
        self.name_lbl.setText(shown)
        self.role_lbl.setText(self._role)
        self.role_lbl.setVisible(bool(self._role))
        self.setToolTip(self._name)

    def add_item(self, text: str, callback, icon: str = "", danger: bool = False):
        self._entries.append(("item", text, icon, danger, callback))
        self._entries_dirty = True

    def add_separator(self):
        self._entries.append(("sep",))
        self._entries_dirty = True

    def clear_items(self):
        self._entries = []
        self._entries_dirty = True

    # ---------- popup plumbing ----------

    def _toggle_popup(self):
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        # A press on the trigger closes an open popup (Qt.Popup behaviour);
        # without this guard the release would immediately re-open it.
        if time.monotonic() - self._closed_at < 0.25:
            return
        self._open_popup()

    def _open_popup(self):
        if self._popup is None:
            self._popup = _UserPopup(self)
            self._entries_dirty = True
        if self._entries_dirty:
            self._popup.set_entries(self._entries)
            self._entries_dirty = False
        self._popup.set_user(self._name, self._role)
        self._open = True
        self.chevron.set_open(True)
        self.update()
        self._popup.popup_below(self)

    def _on_popup_hidden(self):
        self._closed_at = time.monotonic()
        self._open = False
        self.chevron.set_open(False)
        self.update()

    def _on_item_chosen(self, callback):
        if self._popup is not None:
            self._popup.hide()
        if callback is not None:
            # Run after the popup has fully closed so dialogs open cleanly.
            QTimer.singleShot(0, lambda: callback())

    # ---------- interaction ----------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if self.rect().contains(pos):
                self._toggle_popup()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down):
            self._toggle_popup()
            event.accept()
            return
        super().keyPressEvent(event)

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)

    # ---------- theme / paint ----------

    def restyle(self):
        text = _hex("text", "text", "#172033")
        muted = _hex("text_secondary", "text_secondary", "#64748B")
        self.name_lbl.setStyleSheet(
            f"QLabel {{ color: {text}; font-size: 13px; font-weight: 700; background: transparent; }}"
        )
        self.role_lbl.setStyleSheet(
            f"QLabel {{ color: {muted}; font-size: 11px; background: transparent; }}"
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if self._open or self._hover:
                bg = _col("btn_secondary_hover", "surface_alt", "#F1F5F9")
            else:
                bg = _col("surface", "surface", "#FFFFFF")
            if self._open or self.hasFocus():
                border = _col("primary", "primary", "#2563EB")
            else:
                border = _col("border", "border", "#DCE3EC")
            painter.setPen(QPen(border, 1))
            painter.setBrush(QBrush(bg))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        finally:
            painter.end()