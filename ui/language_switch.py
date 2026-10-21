"""
LanguageSwitch — segmented Arabic / English control for the top bar.

Save as ui/language_switch.py. It replaces the old single "🌐 English" button
(`language_toggle_button()` in ui/theme.py, which stays in place for any code
that still uses it).

In ui/shell.py (TopBar), swap the call:

    from ui.language_switch import LanguageSwitch
    ...
    self.lang_switch = LanguageSwitch()      # instead of language_toggle_button()

It reuses the existing flow: it calls ui.main_window.request_language_change()
exactly like the old button did, so persistence (QSettings) and the MainWindow
rebuild keep working unchanged.
"""

from qtpy.QtCore import (
    Qt, QRectF, QEvent, QPropertyAnimation, QAbstractAnimation,
    QEasingCurve, Property,
)
from qtpy.QtGui import QPainter, QColor, QPen, QBrush, QFont, QTextOption
from qtpy.QtWidgets import QWidget, QSizePolicy

from ui.theme import theme, ThemedWidget
from ui import i18n


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _lerp_color(a: QColor, b: QColor, k: float) -> QColor:
    k = _clamp01(k)
    return QColor(
        int(a.red()   + (b.red()   - a.red())   * k),
        int(a.green() + (b.green() - a.green()) * k),
        int(a.blue()  + (b.blue()  - a.blue())  * k),
        int(a.alpha() + (b.alpha() - a.alpha()) * k),
    )


def _tok(name: str, fallback_token: str, default: str) -> QColor:
    """Resolve a theme colour without ever raising inside paintEvent."""
    try:
        pal = theme().palette()
        return QColor(pal.get(name) or pal.get(fallback_token) or default)
    except Exception:
        return QColor(default)


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class LanguageSwitch(ThemedWidget, QWidget):
    """
    Two-segment pill: [ العربية | English ].

    - The active language is a filled primary-colour segment that slides to
      the clicked one (180 ms), then the app language is switched.
    - RTL aware: in an RTL layout the Arabic segment sits on the right.
    - Click a segment, or Tab to focus and press Space / Enter to switch.
    - Hovering the inactive segment gives a soft highlight.
    - Follows language/theme changes (restyle() re-syncs the highlight).
    """

    _W = 152
    _H = 32
    _PAD = 3          # room for the focus ring
    _INSET = 3        # gap between the track and the sliding highlight
    _ANIM_MS = 180

    # Logical order: index 0 = Arabic, index 1 = English.
    _LABELS = ("العربية", "English")

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setObjectName("languageSwitch")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedSize(self._W + 2 * self._PAD, self._H + 2 * self._PAD)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 0.0 = Arabic segment, 1.0 = English segment (tweened).
        self._t = self._current_t()
        self._hover_phys = None      # 0 / 1 = left / right physical half
        self._pressed = False
        self._pending = False

        self._anim = QPropertyAnimation(self, b"lang_t", self)
        self._anim.setDuration(self._ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_anim_finished)

        self._sync_text()
        self._init_theme()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _current_t() -> float:
        return 0.0 if i18n.current_language() == "ar" else 1.0

    def _is_rtl(self) -> bool:
        return self.layoutDirection() == Qt.LayoutDirection.RightToLeft

    def _sync_text(self):
        tip = "Switch to English" if i18n.current_language() == "ar" else "Switch to Arabic"
        self.setToolTip(tip)
        self.setAccessibleName(tip)

    # ------------------------------------------------------------------
    # Animated property
    # ------------------------------------------------------------------

    def get_lang_t(self) -> float:
        return self._t

    def set_lang_t(self, value: float):
        self._t = _clamp01(float(value))
        self.update()

    lang_t = Property(float, get_lang_t, set_lang_t)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    @staticmethod
    def _event_pos(event):
        return event.position().toPoint() if hasattr(event, "position") else event.pos()

    def _phys_at(self, pos) -> int:
        x = pos.x() - self._PAD
        return 0 if x < self._W / 2.0 else 1

    def _logical_from_phys(self, phys: int) -> int:
        return (1 - phys) if self._is_rtl() else phys

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            pos = self._event_pos(event)
            if self.rect().contains(pos):
                self._select(self._logical_from_phys(self._phys_at(pos)))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        phys = self._phys_at(self._event_pos(event))
        if phys != self._hover_phys:
            self._hover_phys = phys
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_phys = None
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current_logical = 0 if i18n.current_language() == "ar" else 1
            self._select(1 - current_logical)
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LayoutDirectionChange:
            self.update()
        super().changeEvent(event)

    def _select(self, logical: int):
        """logical: 0 = Arabic, 1 = English."""
        if self._pending:
            return
        current_logical = 0 if i18n.current_language() == "ar" else 1
        if logical == current_logical:
            return  # already on this language
        self._pending = True
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(float(logical))
        self._anim.start()

    def _on_anim_finished(self):
        if not self._pending:
            return
        self._pending = False
        # Same call the old button made. It rebuilds MainWindow, which destroys
        # this widget — so nothing may touch `self` after this line.
        from ui.main_window import request_language_change
        request_language_change()

    # ------------------------------------------------------------------
    # ThemedWidget contract
    # ------------------------------------------------------------------

    def restyle(self):
        if self._anim.state() != QAbstractAnimation.State.Running:
            self._t = self._current_t()
        self._sync_text()
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        track_bg = _tok("surface_alt", "surface", "#F1F5F9")
        border = _tok("border", "border", "#DCE3EC")
        primary = _tok("primary", "primary", "#2563EB")
        text_secondary = _tok("text_secondary", "text_secondary", "#64748B")
        on_primary = _tok("text_on_primary", "text_on_primary", "#FFFFFF")

        rtl = self._is_rtl()
        k = self._t
        frac = (1.0 - k) if rtl else k          # physical position, 0 = left

        w = float(self._W)
        h = float(self._H)
        inset = float(self._INSET)
        seg_w = (w - 2 * inset) / 2.0
        seg_h = h - 2 * inset

        def seg_x(phys_frac: float) -> float:
            return inset + seg_w * phys_frac

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.translate(self._PAD, self._PAD)

            # ---- track ----
            track_rect = QRectF(0, 0, w, h)
            painter.setPen(QPen(border, 1))
            painter.setBrush(QBrush(track_bg))
            painter.drawRoundedRect(track_rect.adjusted(0.5, 0.5, -0.5, -0.5), h / 2.0, h / 2.0)

            # ---- hover highlight on the inactive segment ----
            if self._hover_phys is not None and not self._pending:
                active_phys = 1 if frac > 0.5 else 0
                if self._hover_phys != active_phys:
                    soft = QColor(primary)
                    soft.setAlpha(34)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(soft))
                    painter.drawRoundedRect(
                        QRectF(seg_x(self._hover_phys), inset, seg_w, seg_h),
                        seg_h / 2.0, seg_h / 2.0,
                    )

            # ---- sliding active highlight ----
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(primary))
            painter.drawRoundedRect(
                QRectF(seg_x(frac), inset, seg_w, seg_h),
                seg_h / 2.0, seg_h / 2.0,
            )

            # ---- labels (colour follows the highlight as it slides) ----
            font = QFont(self.font())
            font.setPixelSize(13)
            option = QTextOption(Qt.AlignmentFlag.AlignCenter)
            for logical, label in enumerate(self._LABELS):
                phys = (1 - logical) if rtl else logical
                closeness = _clamp01(1.0 - abs(frac - phys))
                font.setBold(closeness > 0.5)
                painter.setFont(font)
                painter.setPen(_lerp_color(text_secondary, on_primary, closeness))
                painter.drawText(
                    QRectF(seg_x(float(phys)), inset, seg_w, seg_h), label, option,
                )

            # ---- keyboard focus ring ----
            if self.hasFocus():
                painter.setPen(QPen(primary, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(track_rect.adjusted(-2, -2, 2, 2),
                                        h / 2.0 + 2, h / 2.0 + 2)
        finally:
            painter.end()