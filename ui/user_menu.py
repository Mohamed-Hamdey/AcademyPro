"""
UserMenuButton — top-bar user widget with a custom popup card.
"""

import os
import time

from qtpy.QtCore import Qt, QRectF, QPointF, QPoint, QTimer, QSize
from qtpy.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QTextOption,
    QPixmap, QPainterPath,
)
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
    """
    Circle that shows either the user's photo (clipped to a circle) or,
    if no photo is available, their initial letter on a coloured disc.
    """

    def __init__(self, size: int, parent=None):
        QWidget.__init__(self, parent)
        self._size = size
        self._text = "?"
        self._color = QColor(_AVATAR_COLORS[0])
        self._pixmap: QPixmap | None = None
        self.setFixedSize(size, size)

    def set_user(self, name: str, photo_path: str | None = None):
        name = (name or "").strip()
        self._text = name[:1].upper() if name else "?"
        idx = (sum(ord(ch) for ch in name) % len(_AVATAR_COLORS)) if name else 0
        self._color = QColor(_AVATAR_COLORS[idx])

        self._pixmap = None
        if photo_path and os.path.isfile(photo_path):
            pix = QPixmap(photo_path)
            if not pix.isNull():
                pix = pix.scaled(
                    QSize(self._size, self._size),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._pixmap = pix
        self.update()

    def paintEvent(self, event):
        s = float(self._size)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            circle = QRectF(0, 0, s, s)

            if self._pixmap is not None:
                # Clip the photo to a circle, then blit it centered.
                clip = QPainterPath()
                clip.addEllipse(circle)
                painter.setClipPath(clip)
                # Center-crop the pixmap if it isn't square.
                pw, ph = self._pixmap.width(), self._pixmap.height()
                side = min(pw, ph)
                sx = (pw - side) // 2
                sy = (ph - side) // 2
                painter.drawPixmap(
                    0, 0, self._pixmap,
                    sx, sy, side, side,
                )
            else:
                # Initial-on-colour fallback.
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self._color))
                painter.drawEllipse(circle)

                font = QFont(self.font())
                font.setPixelSize(max(10, int(s * 0.42)))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(
                    circle, self._text,
                    QTextOption(Qt.AlignmentFlag.AlignCenter),
                )
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
    _M = 14
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

    def set_user(self, name: str, role: str, photo_path: str | None = None):
        self.header_avatar.set_user(name, photo_path)
        self.name_lbl.setText(name or "")
        self.role_lbl.setText(role or "")
        self.role_lbl.setVisible(bool(role))

    def _clear_items(self):
        self._rows = []
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
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
        self._photo_path: str | None = None

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

    def set_user(self, name: str, role: str = "", photo_path: str | None = None):
        self._name = name or ""
        self._role = role or ""
        self._photo_path = photo_path
        self.avatar.set_user(self._name, self._photo_path)

        font = QFont(self.font())
        font.setPixelSize(13)
        font.setBold(True)
        shown = QFontMetrics(font).elidedText(self._name, Qt.TextElideMode.ElideRight, 140)
        self.name_lbl.setText(shown)
        self.role_lbl.setText(self._role)
        self.role_lbl.setVisible(bool(self._role))
        self.setToolTip(self._name)

    def set_photo(self, photo_path: str | None):
        self._photo_path = photo_path
        self.avatar.set_user(self._name, self._photo_path)
        if self._popup is not None:
            self._popup.set_user(self._name, self._role, self._photo_path)

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
        self._popup.set_user(self._name, self._role, self._photo_path)
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