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
from PyQt6.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ui.design import SPACING, RADIUS, TYPOGRAPHY
from ui.theme import theme, make_danger, make_secondary, make_ghost


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
        self._build_ui()
        theme().on_change(lambda _m: self._restyle())
        self._restyle()

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

        self.header.setVisible(bool(self._title_text) or bool(self._subtitle_text))
        outer.addWidget(self.header)

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

    def __init__(self, title: str, value: str = "0", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("kpiCard")
        self._build_ui(title, value, subtitle)
        theme().on_change(lambda _m: self._restyle())
        self._restyle()

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
        self.value_label.setStyleSheet(
            f"QLabel#kpiValue {{"
            f"  color: {tm.color('text')};"
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

        theme().on_change(lambda _m: self._restyle())
        self._restyle()

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
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme().on_change(lambda _m: self._restyle())
        self._restyle()

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