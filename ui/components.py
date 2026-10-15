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
    PageHeader    — title + subtitle + action (rarely used directly)
    Button factories: primary_button / secondary_button / ghost_button / danger_button
    hairline()    — themed divider

Legacy names for v1 code (Card, StatusPill, StatCard) are aliased in
ui/widgets.py so old screens keep working during the migration.
"""

import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal

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
# MiniBarChart — simple bar chart for daily values over a window
# ===========================================================================

# ===========================================================================
# MiniBarChart — simple bar chart for daily values over a window
# ===========================================================================

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

    slotClicked = pyqtSignal(object)

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