"""
Reusable UI components built on the design tokens.

Screens compose from these. The goal: no raw QLabel / QFrame styling in
screens — everything comes from here so the design stays consistent.

Components:
    SectionCard   — titled surface with a body
    Toolbar       — horizontal control strip (search + filters + actions)
    KpiCard       — compact metric card
    EmptyState    — centered empty-table/list placeholder
    Pill          — semantic status badge
    BarList       — horizontal bars with labels and values
    ComboBarChart — grouped bar chart with optional click-to-navigate
    Button factories: primary_button / secondary_button / ghost_button / danger_button
    hairline()    — themed divider
"""

import os
import sys

from qtpy.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,QStyledItemDelegate
)
from qtpy.QtGui import QColor, QPainter, QFont, QFontMetrics,QPen
from qtpy.QtCore import Qt, QRectF,Signal,QTimer



from ui.i18n import t

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ui.design import SPACING, RADIUS, TYPOGRAPHY
from ui.theme import ThemedWidget, theme, make_danger, make_secondary, make_ghost


# ===========================================================================
# SectionCard
# ===========================================================================

class SectionCard(QFrame):
    """
    A rounded surface with an optional title row and a body layout.

    Usage:
        card = SectionCard(title="Recent Check-ins")
        card.body.addWidget(some_widget)
    """

    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("sectionCard")
        self._title_text = title
        self._subtitle_text = subtitle
        self._styled = False
        self._build_ui()
        theme().on_change(lambda _m: self._restyle())
        if self.parent() is not None:
            self._restyle()
            self._styled = True
        # else: style will be applied on first show

    def showEvent(self, event):
        super().showEvent(event)
        if not self._styled:
            self._restyle()
            self._styled = True

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["lg"]
        )
        outer.setSpacing(SPACING["md"])

        self.header = QWidget()
        self.header.setObjectName("sectionCardHeader")
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)

        self.title_label = QLabel(self._title_text)
        self.title_label.setObjectName("sectionCardTitle")
        self.subtitle_label = QLabel(self._subtitle_text)
        self.subtitle_label.setObjectName("sectionCardSubtitle")

        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.subtitle_label)

        outer.addWidget(self.header)
        self.header.setVisible(bool(self._title_text) or bool(self._subtitle_text))

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(SPACING["sm"])
        outer.addLayout(self.body)

    def set_title(self, text: str):
        self._title_text = text
        self.title_label.setText(text)
        self.header.setVisible(bool(text) or bool(self._subtitle_text))

    def set_subtitle(self, text: str):
        self._subtitle_text = text
        self.subtitle_label.setText(text)
        self.header.setVisible(bool(self._title_text) or bool(text))

    def _restyle(self):
        tm = theme()
        self.setStyleSheet(
            f"QFrame#sectionCard {{"
            f"  background-color: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['lg']}px;"
            f"}}"
            f"QWidget#sectionCardHeader {{"
            f"  background-color: transparent;"
            f"}}"
        )
        self.title_label.setStyleSheet(
            f"QLabel#sectionCardTitle {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['card_title']['size']}px;"
            f"  font-weight: 600;"
            f"}}"
        )
        self.subtitle_label.setStyleSheet(
            f"QLabel#sectionCardSubtitle {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['meta']['size']}px;"
            f"}}"
        )


# ===========================================================================
# Toolbar
# ===========================================================================

class Toolbar(QWidget):
    """
    Horizontal control strip. Start side holds search + filters; end side
    holds the primary action. Qt layouts mirror automatically under RTL.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])

        self.start_layout = QHBoxLayout()
        self.start_layout.setSpacing(SPACING["sm"])
        self.end_layout = QHBoxLayout()
        self.end_layout.setSpacing(SPACING["sm"])

        layout.addLayout(self.start_layout, stretch=1)
        layout.addLayout(self.end_layout)

    def add_leading(self, widget: QWidget, stretch: int = 0):
        self.start_layout.addWidget(widget, stretch=stretch)

    def add_trailing(self, widget: QWidget):
        self.end_layout.addWidget(widget)


# ===========================================================================
# KpiCard
# ===========================================================================

class KpiCard(QFrame):
    """
    Compact metric card: title, big value, optional subtitle.

    Usage:
        card = KpiCard("Total Revenue", "1,250 EGP", subtitle="today")
        card.set_value("1,400 EGP")
    """

    def __init__(self, title: str, value: str = "0", subtitle: str = "",
                parent=None, value_color: str = None):
        """
        value_color: optional theme token name (e.g. "success", "danger",
        "primary") for the big value label. When None, the value uses the
        default "text" token.
        """
        super().__init__(parent)
        self.setObjectName("kpiCard")
        self._value_color = value_color
        self._styled = False
        self._build_ui(title, value, subtitle)
        theme().on_change(lambda _m: self._restyle())
        if self.parent() is not None:
            self._restyle()
            self._styled = True

    def showEvent(self, event):
        super().showEvent(event)
        if not self._styled:
            self._restyle()
            self._styled = True

    def _build_ui(self, title, value, subtitle):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"]
        )
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("kpiTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("kpiValue")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("kpiSubtitle")
        self.subtitle_label.setVisible(bool(subtitle))

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)

    def set_value(self, value):
        self.value_label.setText(str(value))

    def set_subtitle(self, text: str):
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))

    def _restyle(self):
        tm = theme()
        self.setStyleSheet(
            f"QFrame#kpiCard {{"
            f"  background-color: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['md']}px;"
            f"}}"
        )
        self.title_label.setStyleSheet(
            f"QLabel#kpiTitle {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['label']['size']}px;"
            f"  font-weight: 600;"
            f"}}"
        )
        value_color = tm.color(self._value_color) if self._value_color else tm.color("text")
        self.value_label.setStyleSheet(
            f"QLabel#kpiValue {{"
            f"  color: {value_color};"
            f"  background-color: transparent;"
            f"  font-size: 22px;"
            f"  font-weight: 700;"
            f"}}"
        )
        self.subtitle_label.setStyleSheet(
            f"QLabel#kpiSubtitle {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['meta']['size']}px;"
            f"}}"
        )


# ===========================================================================
# EmptyState
# ===========================================================================

class EmptyState(QWidget):
    """Centered icon + message, optionally with a call-to-action button."""

    def __init__(self, icon: str = "📭", message: str = "",
                 action_text: str = "", on_action=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACING["sm"])

        self.icon_label = QLabel(icon)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        self.action_button = None
        if action_text and on_action:
            self.action_button = QPushButton(action_text)
            self.action_button.clicked.connect(on_action)
            layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self._styled = False
        theme().on_change(lambda _m: self._restyle())
        if self.parent() is not None:
            self._restyle()
            self._styled = True
        # else: style will be applied on first show

    def showEvent(self, event):
        super().showEvent(event)
        if not self._styled:
            self._restyle()
            self._styled = True

    def _restyle(self):
        tm = theme()
        self.icon_label.setStyleSheet(
            f"QLabel {{"
            f"  font-size: 36px;"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"}}"
        )
        self.message_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['body']['size']}px;"
            f"}}"
        )


# ===========================================================================
# Pill
# ===========================================================================

class Pill(QLabel):
    """
    Small semantic status badge.
    kind: success | warning | error | info | primary | neutral
    """

    _SOFT = {
        "success": "success_soft",
        "warning": "warning_soft",
        "error":   "error_soft",
        "danger":  "danger_soft",
        "info":    "info_soft",
        "primary": "primary_soft",
        "neutral": "neutral_soft",
        "muted":   "neutral_soft",
    }
    _TEXT = {
        "success": "success",
        "warning": "warning",
        "error":   "error",
        "danger":  "danger",
        "info":    "info",
        "primary": "primary",
        "neutral": "text_secondary",
        "muted":   "text_secondary",
    }

    def __init__(self, text: str = "", kind: str = "neutral", parent=None):
        super().__init__(text, parent)
        self._kind = kind
        self._styled = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme().on_change(lambda _m: self._restyle())
        if self.parent() is not None:
            self._restyle()
            self._styled = True
        # else: style will be applied on first show

    def showEvent(self, event):
        super().showEvent(event)
        if not self._styled:
            self._restyle()
            self._styled = True

    def set_status(self, text: str, kind: str):
        self._kind = kind
        self.setText(text)
        self._restyle()

    def _restyle(self):
        tm = theme()
        text_token = self._TEXT.get(self._kind, "text_secondary")
        bg_token = self._SOFT.get(self._kind, "neutral_soft")
        self.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color(text_token)};"
            f"  background-color: {tm.color(bg_token)};"
            f"  border: none;"
            f"  border-radius: 10px;"
            f"  padding: 3px 10px;"
            f"  font-weight: 700;"
            f"  font-size: 11px;"
            f"}}"
        )


# ===========================================================================
# Button factories
# ===========================================================================

def primary_button(text: str) -> QPushButton:
    return QPushButton(text)


def secondary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    make_secondary(btn)
    return btn


def ghost_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    make_ghost(btn)
    return btn


def danger_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    make_danger(btn)
    return btn


# ===========================================================================
# hairline
# ===========================================================================

def hairline(parent=None) -> QFrame:
    line = QFrame(parent)
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)

    def _restyle():
        line.setStyleSheet(
            f"background-color: {theme().color('divider')}; border: none;"
        )

    _restyle()
    theme().on_change(lambda _m: _restyle())
    return line

# ===========================================================================
# BarList — horizontal bars with labels and values
# ===========================================================================

class BarList(QWidget, ThemedWidget):
    """
    A vertical stack of horizontal bars. Each row shows:
        label                        1,650 EGP · 69% (2)
        ████████████░░░░░░░░░        XX%

    Data shape: list of dicts with keys:
        - label       (str)
        - value       (float)
        - count       (int, optional)
        - suffix      (str, optional)
        - color       (str, optional)

    Rows are sorted by value descending before rendering.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACING["sm"])
        self._styled = False
        if self.parent() is not None:
            self._init_theme()
            self._styled = True
        # else: style will be applied on first show

    def showEvent(self, event):
        super().showEvent(event)
        if not self._styled:
            self._init_theme()
            self._styled = True

    def set_data(self, rows: list):
        self._rows = sorted(rows, key=lambda r: r.get("value", 0), reverse=True)
        self._render()

    def restyle(self):
        self._render()

    # ---------- internal ----------

    def _clear(self):
        """Remove every child widget immediately, not on the next tick."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        # Belt-and-braces: any widget still parented to self that isn't
        # in the layout (shouldn't happen, but Qt is Qt).
        for child in self.findChildren(QWidget):
            child.setParent(None)
            child.deleteLater()

    def _render(self):
        # 1. Always clear first — no matter how we got here.
        self._clear()

        # 2. Empty state
        if not self._rows:
            tm = theme()
            lbl = QLabel(t("dash.no_data"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text_secondary')};"
                f"  background-color: transparent;"
                f"  font-style: italic;"
                f"  padding: 24px 8px;"
                f"}}"
            )
            self._layout.addWidget(lbl)
            return

        # 3. Draw rows
        tm = theme()
        total = sum(r["value"] for r in self._rows) or 1.0

        for i, r in enumerate(self._rows):
            row = QWidget()
            v = QVBoxLayout(row)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(4)

            top = QHBoxLayout()
            top.setContentsMargins(0, 0, 0, 0)
            top.setSpacing(8)

            label = QLabel(r["label"])
            label.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text')};"
                f"  background-color: transparent;"
                f"  font-size: 13px;"
                f"  font-weight: 600;"
                f"}}"
            )
            top.addWidget(label)
            top.addStretch()

            suffix = r.get("suffix", "")
            value_text = f"{r['value']:,.0f}{suffix}"
            pct = (r["value"] / total) * 100
            pct_text = f"{pct:.0f}%"
            extra_bits = [pct_text]
            if r.get("count") is not None:
                extra_bits.append(f"({r['count']})")
            value_full = f"{value_text}  ·  " + "  ".join(extra_bits)

            value_lbl = QLabel(value_full)
            value_lbl.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text_secondary')};"
                f"  background-color: transparent;"
                f"  font-size: 12px;"
                f"  font-weight: 600;"
                f"}}"
            )
            top.addWidget(value_lbl)
            v.addLayout(top)

            bar_bg = QFrame()
            bar_bg.setFixedHeight(8)
            bar_bg.setStyleSheet(
                f"QFrame {{"
                f"  background-color: {tm.color('surface_alt')};"
                f"  border-radius: 4px;"
                f"}}"
            )
            bar_bg_layout = QHBoxLayout(bar_bg)
            bar_bg_layout.setContentsMargins(0, 0, 0, 0)
            bar_bg_layout.setSpacing(0)

            fill_pct = max(0.02, r["value"] / total)
            fill = QFrame()
            fill.setStyleSheet(
                f"QFrame {{"
                f"  background-color: {tm.color(r.get('color', 'primary'))};"
                f"  border-radius: 4px;"
                f"}}"
            )
            fill.setMinimumWidth(4)

            stretch_fill = int(fill_pct * 1000)
            stretch_rest = int((1 - fill_pct) * 1000)
            bar_bg_layout.addWidget(fill, stretch=stretch_fill)
            if stretch_rest > 0:
                bar_bg_layout.addStretch(stretch_rest)

            v.addWidget(bar_bg)
            self._layout.addWidget(row)



# ===========================================================================
# ComboBarChart — grouped bars + optional net line
# ===========================================================================

class ComboBarChart(QWidget, ThemedWidget):
    """
    A compact bar chart with:
      - 1 or 2 grouped bar series per x-slot (e.g. revenue + expenses)
      - Highlighted slot (the currently-selected day)
      - Click handler that emits the slot's `key`

    Data shape:
        slots = [
            {
                "label":     str,           # short x-axis label
                "key":       any,           # returned on click
                "values":    [float, ...],  # one value per series, in order
                "highlight": bool,          # draw emphasized
            },
            ...
        ]
    """

    slotClicked = Signal(object)

    def __init__(self, height: int = 130, series_labels=None,
                 series_colors=None, show_net_line: bool = False,
                 parent=None):
        super().__init__(parent)
        self._height = height
        self._series_labels = series_labels or []
        self._series_colors = series_colors or ["primary", "border"]
        self._show_net_line = show_net_line
        self._slots = []
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 8, 0, 0)
        self._layout.setSpacing(SPACING["sm"])
        self.setMinimumHeight(height + 42)
        self._styled = False
        if self.parent() is not None:
            self._init_theme()
            self._styled = True
        # else: style will be applied on first show

    def showEvent(self, event):
        super().showEvent(event)
        if not self._styled:
            self._init_theme()
            self._styled = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(self, slots: list):
        """Replace the chart contents. Always clears first via _render()."""
        self._slots = list(slots)
        self._render()

    def restyle(self):
        """Called automatically on theme change."""
        self._render()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _clear(self):
        """
        Remove every child widget from the layout AND from this widget's
        ownership, immediately. This is the only reliable way to prevent
        Qt from showing duplicated content across multiple _render() calls.
        """
        # Take every item out of the layout and unparent it.
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        # Belt-and-braces: any widget still parented to self but not in the
        # layout (rare, but Qt sometimes leaves these behind).
        for child in self.findChildren(QWidget):
            child.setParent(None)
            child.deleteLater()

    def _render(self):
        # 1. Clear first — ALWAYS. This is what prevents duplication.
        self._clear()

        # 2. Empty case: show a dash.
        if not self._slots:
            tm = theme()
            lbl = QLabel("—")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text_secondary')};"
                f"  background-color: transparent;"
                f"  font-size: 12px;"
                f"}}"
            )
            self._layout.addWidget(lbl)
            return

        # 3. Compute shared max across all series for a consistent scale.
        max_val = 0.0
        for s in self._slots:
            for v in s.get("values", []):
                if v and v > max_val:
                    max_val = v
        all_zero = (max_val == 0)

        tm = theme()

        # 4. Draw one slot column per data point.
        for s in self._slots:
            col = QWidget()
            col.setCursor(Qt.CursorShape.PointingHandCursor)
            col.setSizePolicy(
                col.sizePolicy().horizontalPolicy(),
                col.sizePolicy().verticalPolicy().Preferred,
            )

            v = QVBoxLayout(col)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(2)

            # ---- value row (above bars) ----
            values = s.get("values", [])
            if values and not all_zero:
                shown = [f"{x:,.0f}" for x in values if x]
                top_text = " · ".join(shown)
            else:
                top_text = ""
            top = QLabel(top_text)
            top.setAlignment(Qt.AlignmentFlag.AlignCenter)
            top.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text_secondary')};"
                f"  background-color: transparent;"
                f"  font-size: 10px;"
                f"  font-weight: 600;"
                f"}}"
            )
            v.addWidget(top)

            # ---- bar area (fixed height, bars sit on the baseline) ----
            bar_area = QWidget()
            bar_area.setFixedHeight(self._height)
            ba = QHBoxLayout(bar_area)
            ba.setContentsMargins(0, 0, 0, 0)
            ba.setSpacing(0)
            ba.addStretch()

            # inner column: stretch pushes the bar group down to the bottom
            bar_col = QVBoxLayout()
            bar_col.setContentsMargins(0, 0, 0, 0)
            bar_col.setSpacing(0)
            bar_col.addStretch()

            bars_row = QHBoxLayout()
            bars_row.setContentsMargins(0, 0, 0, 0)
            bars_row.setSpacing(2)

            for i, val in enumerate(values):
                bar = QFrame()
                if all_zero or not val:
                    bar_px = 2
                else:
                    bar_px = max(4, int((val / max_val) * (self._height - 6)))
                bar.setFixedHeight(bar_px)
                bar.setFixedWidth(14)
                color_token = self._series_colors[i % len(self._series_colors)]
                bar.setStyleSheet(
                    f"QFrame {{"
                    f"  background-color: {tm.color(color_token)};"
                    f"  border-radius: 2px;"
                    f"}}"
                )
                bars_row.addWidget(bar)

            bar_col.addLayout(bars_row)
            ba.addLayout(bar_col)
            ba.addStretch()

            v.addWidget(bar_area)

            # ---- x-axis label (below bars) ----
            x_label = QLabel(s.get("label", ""))
            x_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            x_label.setStyleSheet(
                f"QLabel {{"
                f"  color: {tm.color('text_secondary')};"
                f"  background-color: transparent;"
                f"  font-size: 11px;"
                f"}}"
            )
            v.addWidget(x_label)

            # ---- click handler ----
            key = s.get("key")
            def _make_handler(k):
                def _handler(event):
                    self.slotClicked.emit(k)
                return _handler
            col.mousePressEvent = _make_handler(key)

            self._layout.addWidget(col)
            
            
class PillDelegate(QStyledItemDelegate):
    """
    Draws a colored Pill inside a table cell.
    Supports both standard statuses and championship medals.

    Expects the cell's QTableWidgetItem to have data(UserRole) set to
    a dict: {"text": str, "kind": "success"|"danger"|"gold"|...}.
    """

    _SOFT = {
        "success": "success_soft", "warning": "warning_soft",
        "error": "error_soft", "danger": "danger_soft",
        "info": "info_soft", "primary": "primary_soft",
        "neutral": "neutral_soft",
        # Medal additions:
        "gold": "medal_gold_soft", "silver": "medal_silver_soft", "bronze": "medal_bronze_soft"
    }
    _TEXT = {
        "success": "success", "warning": "warning",
        "error": "error", "danger": "danger",
        "info": "info", "primary": "primary",
        "neutral": "text_secondary",
        # Medal additions:
        "gold": "medal_gold", "silver": "medal_silver", "bronze": "medal_bronze"
    }

    def paint(self, painter, option, index):
        data = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            super().paint(painter, option, index)
            return

        text = data.get("text", "")
        kind = data.get("kind", "neutral")

        tm = theme()
        # Fallbacks ensure it never crashes if a color is missing
        fg = QColor(tm.color(self._TEXT.get(kind, "text_secondary")))
        bg = QColor(tm.color(self._SOFT.get(kind, "neutral_soft")))

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        font = QFont(option.font)
        base_px = font.pixelSize()
        if base_px <= 0:
            base_px = 13
        font.setPixelSize(max(9, int(base_px * 0.85)))
        font.setBold(True)
        painter.setFont(font)

        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(text)
        pad_x = 12
        pad_y = 4
        pill_w = text_w + pad_x * 2
        pill_h = fm.height() + pad_y * 2

        r = option.rect
        margin = 6
        max_w = r.width() - margin * 2

        if pill_w > max_w:
            while pill_w > max_w and font.pixelSize() > 8:
                font.setPixelSize(font.pixelSize() - 1)
                painter.setFont(font)
                fm = QFontMetrics(font)
                text_w = fm.horizontalAdvance(text)
                pill_w = text_w + pad_x * 2
                pill_h = fm.height() + pad_y * 2
            pill_w = min(pill_w, max_w)

        pill_rect = QRectF(
            r.center().x() - pill_w / 2,
            r.center().y() - pill_h / 2,
            pill_w, pill_h,
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        radius = pill_h / 2
        painter.drawRoundedRect(pill_rect, radius, radius)

        painter.setPen(QPen(fg))
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()
        
        
"""
ThemeToggleSwitch — animated Light/Dark pill switch.

Drop-in replacement for the old class. If this class lives in
ui/components.py, merge the imports below with the ones already there
(most of them are probably present already) and paste the class over the old one.
"""

import math

from qtpy.QtCore import (
    Qt, QRectF, QLineF, QPointF, QEvent, QPropertyAnimation,
    QAbstractAnimation, QEasingCurve, Property,
)
from qtpy.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush
from qtpy.QtWidgets import QWidget, QSizePolicy

from ui.theme import theme, ThemedWidget
from ui.i18n import t


# ---------------------------------------------------------------------------
# Small helpers
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
    """
    Resolve a colour without ever raising: try the dedicated toggle token,
    then an existing design token, then a hard default. (theme().color()
    raises KeyError on unknown tokens, and an exception inside paintEvent
    can abort a PyQt6 app.)
    """
    try:
        pal = theme().palette()
        return QColor(pal.get(name) or pal.get(fallback_token) or default)
    except Exception:
        return QColor(default)


def _draw_sun(p: QPainter, cx: float, cy: float, r: float, color: QColor, rotation: float = 0.0):
    p.save()
    p.translate(cx, cy)
    p.rotate(rotation)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color))
    core = r * 0.62
    p.drawEllipse(QPointF(0, 0), core, core)

    p.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    for i in range(8):
        a = math.radians(i * 45)
        c, s = math.cos(a), math.sin(a)
        p.drawLine(QLineF(c * r * 0.98, s * r * 0.98, c * r * 1.40, s * r * 1.40))
    p.restore()


def _draw_moon(p: QPainter, cx: float, cy: float, r: float, color: QColor):
    """A real crescent: a disc with an offset disc cut out of it."""
    outer = QPainterPath()
    outer.addEllipse(QPointF(cx, cy), r * 1.10, r * 1.10)
    cut = QPainterPath()
    cut.addEllipse(QPointF(cx + r * 0.55, cy - r * 0.45), r * 0.95, r * 0.95)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color))
    p.drawPath(outer.subtracted(cut))


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class ThemeToggleSwitch(ThemedWidget, QWidget):
    """
    Animated pill-shaped Light/Dark toggle.

    Visual:
      - Rounded track: slate when light mode, primary colour when dark mode.
      - White knob that slides between the ends. The knob shows a sun in
        light mode and a crescent moon in dark mode (cross-fades while sliding,
        the sun rotates a little).
      - The *other* mode's icon sits faintly on the empty end of the track,
        so both states are always readable.

    Behaviour:
      - Click (release inside the widget), Space, Enter or Return toggles.
      - The knob animates FIRST (200 ms, OutCubic); the theme is swapped when
        the animation finishes. Swapping the theme repaints the whole app and
        blocks the event loop, so doing it mid-animation made the knob jump.
      - RTL aware: in an RTL layout the knob travels right-to-left.
      - Keyboard focus ring (Tab only; not shown after a mouse click).
      - Follows theme changes made elsewhere (restyle() re-syncs the knob).

    Optional design tokens (each falls back to an existing token):
      toggle_active   -> primary
      toggle_inactive -> text_disabled
      toggle_knob     -> text_on_primary
    """

    _TRACK_W = 58
    _TRACK_H = 30
    _PAD = 3              # space around the track, used by the focus ring
    _KNOB_MARGIN = 4
    _ANIM_MS = 160

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setObjectName("themeToggleSwitch")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedSize(self._TRACK_W + 2 * self._PAD, self._TRACK_H + 2 * self._PAD)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 0.0 = light mode, 1.0 = dark mode (tweened by the animation).
        self._knob_t = 1.0 if theme().is_dark() else 0.0
        self._hover = False
        self._pressed = False
        self._pending_toggle = False

        self._anim = QPropertyAnimation(self, b"knob_t", self)
        self._anim.setDuration(self._ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_anim_finished)

        self._sync_text()
        self._init_theme()

    # ------------------------------------------------------------------
    # Animated property
    # ------------------------------------------------------------------

    def get_knob_t(self) -> float:
        return self._knob_t

    def set_knob_t(self, value: float):
        self._knob_t = _clamp01(float(value))
        self.update()

    knob_t = Property(float, get_knob_t, set_knob_t)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

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
                self._toggle()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._toggle()
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

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LayoutDirectionChange:
            self.update()
        super().changeEvent(event)

    def _toggle(self):
        if self._pending_toggle:
            return
        self._pending_toggle = True
        target = 0.0 if theme().is_dark() else 1.0
        self._anim.stop()
        self._anim.setStartValue(self._knob_t)
        self._anim.setEndValue(target)
        self._anim.start()
        # Kick off the theme swap NOW. It's the expensive part; start it
        # while the knob is already moving so the user perceives it as instant.
        QTimer.singleShot(0, theme().toggle)

    def _on_anim_finished(self):
        self._pending_toggle = False
        # No theme().toggle() here anymore — it already fired.

    # ------------------------------------------------------------------
    # ThemedWidget contract
    # ------------------------------------------------------------------

    def _sync_text(self):
        dark = theme().is_dark()
        tip = t("theme.switch_to_light") if dark else t("theme.switch_to_dark")
        self.setToolTip(tip)
        self.setAccessibleName(tip)

    def restyle(self):
        # Keep the knob in sync when the theme was changed elsewhere
        # (other toggle button, startup, etc.), but never fight a running animation.
        if self._anim.state() != QAbstractAnimation.State.Running:
            self._knob_t = 1.0 if theme().is_dark() else 0.0
        self._sync_text()
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        active = _tok("toggle_active", "primary", "#2563EB")
        inactive = _tok("toggle_inactive", "text_disabled", "#94A3B8")
        knob_color = _tok("toggle_knob", "text_on_primary", "#FFFFFF")
        sun_color = QColor("#F59E0B")
        moon_color = active.darker(115)

        k = self._knob_t
        rtl = self.layoutDirection() == Qt.LayoutDirection.RightToLeft

        w = float(self._TRACK_W)
        h = float(self._TRACK_H)
        m = float(self._KNOB_MARGIN)
        knob_d = h - m * 2
        left_cx = m + knob_d / 2.0
        travel = w - m * 2 - knob_d

        def cx_for(tt: float) -> float:
            frac = (1.0 - tt) if rtl else tt
            return left_cx + travel * frac

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.translate(self._PAD, self._PAD)

            # ---- track ----
            track = _lerp_color(inactive, active, k)
            if self._hover:
                track = track.lighter(108)
            track_rect = QRectF(0, 0, w, h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(track))
            painter.drawRoundedRect(track_rect, h / 2.0, h / 2.0)

            # ---- faint icons for the mode the knob is NOT on ----
            r = knob_d * 0.26
            cy = h / 2.0
            white = QColor("#FFFFFF")
            painter.setOpacity(_clamp01(1.0 - k) * 0.75)
            _draw_moon(painter, cx_for(1.0), cy, r * 0.95, white)
            painter.setOpacity(_clamp01(k) * 0.75)
            _draw_sun(painter, cx_for(0.0), cy, r * 0.95, white)
            painter.setOpacity(1.0)

            # ---- knob (two-layer soft shadow + fill) ----
            kcx = cx_for(k)
            kr = knob_d / 2.0
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 18))
            painter.drawEllipse(QPointF(kcx, cy + 0.8), kr + 0.8, kr + 0.8)
            painter.setBrush(QColor(0, 0, 0, 28))
            painter.drawEllipse(QPointF(kcx, cy + 1.6), kr, kr)
            painter.setBrush(QBrush(knob_color))
            painter.drawEllipse(QPointF(kcx, cy), kr, kr)

            # ---- glyph on the knob: sun -> moon cross-fade ----
            sun_op = _clamp01(1.0 - 2.0 * k)
            moon_op = _clamp01(2.0 * k - 1.0)
            if sun_op > 0.0:
                painter.setOpacity(sun_op)
                _draw_sun(painter, kcx, cy, r, sun_color, rotation=k * 120.0)
            if moon_op > 0.0:
                painter.setOpacity(moon_op)
                _draw_moon(painter, kcx, cy, r, moon_color)
            painter.setOpacity(1.0)

            # ---- keyboard focus ring ----
            if self.hasFocus():
                ring = QColor(_tok("primary", "primary", "#2563EB"))
                painter.setPen(QPen(ring, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(track_rect.adjusted(-2, -2, 2, 2),
                                        h / 2.0 + 2, h / 2.0 + 2)
        finally:
            painter.end()
            
            
class LineChartWidget(QWidget, ThemedWidget):
    """
    A lightweight, painted line chart for weight history.
    Dots are colored according to the belt at that measurement.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._init_theme()

    def set_data(self, data: list):
        """Data is a list of dicts: {'date': str, 'weight': float, 'belt': str}"""
        self._data = data
        self.update()

    def restyle(self):
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            
            tm = theme()
            # Increase bottom padding to make room for the dates
            pad_x = 40
            pad_y_top = 30
            pad_y_bottom = 50  
            w = self.width() - pad_x * 2
            h = self.height() - pad_y_top - pad_y_bottom
            
            # Find min/max for Y axis scaling
            weights = [d["weight"] for d in self._data if d["weight"] is not None]
            if not weights:
                return
            min_w, max_w = min(weights), max(weights)
            if min_w == max_w:
                min_w -= 1
                max_w += 1

            def get_pt(i, d):
                x = pad_x + (i / max(1, len(self._data) - 1)) * w
                y = pad_y_top + h - ((d["weight"] - min_w) / (max_w - min_w)) * h
                return x, y

            # 1. Draw line (Black/Text color)
            painter.setPen(QPen(QColor(tm.color("text")), 2))
            path = QPainterPath()
            for i, d in enumerate(self._data):
                if d["weight"] is None:
                    continue
                x, y = get_pt(i, d)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)

            # 2. Draw dots (colored by belt)
            belt_colors = {
                "white": "#FFFFFF", "yellow": "#FCD34D", "orange": "#F97316",
                "green": "#22C55E", "blue": "#3B82F6", "purple": "#A855F7",
                "brown": "#78350F", "black": "#111827",
            }
            
            # Setup font for date labels
            font = QFont(self.font())
            font.setPixelSize(10)
            painter.setFont(font)

            for i, d in enumerate(self._data):
                if d["weight"] is None:
                    continue
                x, y = get_pt(i, d)
                color = belt_colors.get((d.get("belt") or "white").lower(), "#94A3B8")
                
                # Draw Dot
                painter.setPen(QPen(QColor(tm.color("surface")), 2))
                painter.setBrush(QColor(color))
                painter.drawEllipse(QPointF(x, y), 6, 6)
                
                # 3. Draw Date Label (only if we have a reasonable amount of space)
                date_str = d.get("date", "")[:10] # Grab YYYY-MM-DD
                if date_str:
                    painter.setPen(QColor(tm.color("text_secondary")))
                    # Center the text below the dot
                    text_rect = QRectF(x - 40, y + 10, 80, 20)
                    painter.drawText(
                        text_rect, 
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, 
                        date_str
                    )
                
        finally:
            painter.end()