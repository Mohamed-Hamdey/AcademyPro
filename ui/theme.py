"""
Global app theme (v4.2) — driven by ui/design.py tokens.

What changed in v4.2 (public API is unchanged — every function, class and
constant from v4.1 is still here with the same signature):

  * Icons (combo arrow, spin arrows, checkbox tick) are now generated as
    small PNG files on first use and referenced by file path. Qt style
    sheets do not reliably support `url(data:...)` URIs, which is what
    produced the little square glyphs instead of arrows. The icons are
    drawn with QPainter (no SVG plugin needed, so PyInstaller builds work)
    and are coloured from the active theme tokens.
  * Tables now style QTableView, so QTableWidget AND future QTableView
    screens (delegate based lists) share one look. Added hover, header
    hover, corner button.
  * Inputs: hover / disabled / invalid states, a "search" variant,
    QPlainTextEdit, symmetric combo padding so it works in RTL and LTR.
  * New components styled: QProgressBar (with state colours), QRadioButton,
    QToolButton, QMessageBox, QSplitter, QScrollArea.
  * New button classes: "success" and "segment" (checkable pill used for
    activity tabs / filter chips).
  * New label classes: "muted", "caption", "title".
  * Missing hover/pressed/soft tokens are derived from the base colour
    instead of silently falling back to light-mode hex values.
  * Removed the invalid `QLineEdit::placeholder` rule (placeholder colour
    comes from the palette, set in build_palette()).
"""

from __future__ import annotations

import os
import tempfile
from typing import Callable, Optional

from qtpy.QtCore import QObject, QSettings, Signal, QEasingCurve, QPropertyAnimation, Qt, QPointF
from qtpy.QtGui import QPalette, QColor, QImage, QPainter, QPen, QPolygonF
from qtpy.QtWidgets import (
    QApplication, QPushButton, QWidget, QGraphicsOpacityEffect,
    QGroupBox, QTabWidget, QTableWidget, QHeaderView,
)

from ui.design import tokens, LIGHT, DARK, SPACING, RADIUS, TYPOGRAPHY


# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------
CARD_RADIUS   = RADIUS["lg"]
BUTTON_RADIUS = RADIUS["sm"]
GUTTER        = SPACING["lg"]
SECTION_GAP   = SPACING["xl"]


# ---------------------------------------------------------------------------
# Backward-compat exports
# ---------------------------------------------------------------------------
PRIMARY         = LIGHT["primary"]
PRIMARY_HOVER   = LIGHT["primary_hover"]
PRIMARY_PRESSED = LIGHT["primary_pressed"]

DANGER          = LIGHT["danger"]
DANGER_HOVER    = LIGHT["danger_hover"]
DANGER_PRESSED  = LIGHT["danger_pressed"]

SUCCESS = LIGHT["success"]
WARNING = LIGHT["warning"]
MUTED   = LIGHT["neutral"]

BG             = LIGHT["bg"]
SURFACE        = LIGHT["surface"]
BORDER         = LIGHT["border"]
TEXT_PRIMARY   = LIGHT["text"]
TEXT_SECONDARY = LIGHT["text_secondary"]


# ---------------------------------------------------------------------------
# Icon generation (file based — see module docstring)
# ---------------------------------------------------------------------------

_ICON_DIR = os.path.join(tempfile.gettempdir(), "academy_system_theme_icons")
_icon_cache: dict = {}


def _draw_icon(kind: str, color: str, path: str) -> bool:
    """Draw a small icon with QPainter and save it as PNG. Returns success."""
    size = 18 if kind == "check" else 16
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))

    painter = QPainter(img)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = 2.2 if kind == "check" else 1.8
        pen = QPen(
            QColor(color), width,
            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)

        if kind == "chevron_down":
            pts = [QPointF(4.5, 6.5), QPointF(8.0, 10.0), QPointF(11.5, 6.5)]
        elif kind == "chevron_up":
            pts = [QPointF(4.5, 9.5), QPointF(8.0, 6.0), QPointF(11.5, 9.5)]
        elif kind == "check":
            pts = [QPointF(4.5, 9.5), QPointF(7.8, 12.8), QPointF(13.5, 5.8)]
        else:
            return False

        painter.drawPolyline(QPolygonF(pts))
    finally:
        painter.end()

    return img.save(path, "PNG")


def _icon(kind: str, color: str) -> str:
    """
    Return a QSS value for an icon: `url("<path>")`, or `none` if the icon
    could not be created (the control then simply shows no glyph).
    """
    key = (kind, color.lower())
    if key in _icon_cache:
        return _icon_cache[key]

    value = "none"
    try:
        os.makedirs(_ICON_DIR, exist_ok=True)
        fname = f"{kind}_{color.lstrip('#').lower()}.png"
        path = os.path.join(_ICON_DIR, fname)
        if os.path.exists(path) or _draw_icon(kind, color, path):
            value = 'url("%s")' % path.replace("\\", "/")
    except Exception:
        value = "none"

    _icon_cache[key] = value
    return value


def _shade(hex_color: str, pct: int = 112) -> str:
    """Derive a darker variant of a colour (used for missing hover tokens)."""
    try:
        return QColor(hex_color).darker(pct).name()
    except Exception:
        return hex_color


# ---------------------------------------------------------------------------
# Stylesheet builder
# ---------------------------------------------------------------------------

def _safe(palette: dict, key: str, fallback: str) -> str:
    """Return palette[key] or fallback if the token isn't defined."""
    return palette.get(key, fallback)


def build_stylesheet(mode: str) -> str:
    p = LIGHT if mode == "light" else DARK

    def c(key, fallback):
        return _safe(p, key, fallback)

    fam = tokens.font_family()
    body_size = TYPOGRAPHY["body"]["size"]
    table_size = TYPOGRAPHY["table"]["size"]
    label_size = TYPOGRAPHY["label"]["size"]
    button_size = TYPOGRAPHY["button"]["size"]
    btn_r = RADIUS["sm"]
    input_r = RADIUS["sm"]
    card_r = RADIUS["lg"]

    # ---- tokens ----
    text             = c("text", "#172033")
    text_secondary   = c("text_secondary", "#64748B")
    text_disabled    = c("text_disabled", "#94A3B8")
    text_on_primary  = c("text_on_primary", "#FFFFFF")

    bg               = c("bg", "#F5F7FA")
    surface          = c("surface", "#FFFFFF")
    surface_alt      = c("surface_alt", "#F8FAFC")
    border           = c("border", "#DCE3EC")
    divider          = c("divider", "#E8EDF3")

    primary          = c("primary", "#2563EB")
    primary_hover    = c("primary_hover", _shade(primary))
    primary_pressed  = c("primary_pressed", _shade(primary, 125))
    primary_soft     = c("primary_soft", "#DBEAFE")

    success          = c("success", "#16A34A")
    success_hover    = c("success_hover", _shade(success))
    success_pressed  = c("success_pressed", _shade(success, 125))
    success_soft     = c("success_soft", "#DCFCE7")

    danger           = c("danger", "#DC2626")
    danger_hover     = c("danger_hover", _shade(danger))
    danger_pressed   = c("danger_pressed", _shade(danger, 125))
    danger_soft      = c("danger_soft", "#FEE2E2")

    warning          = c("warning", "#D97706")
    warning_hover    = c("warning_hover", _shade(warning))
    warning_pressed  = c("warning_pressed", _shade(warning, 125))
    warning_soft     = c("warning_soft", "#FEF3C7")

    neutral_soft     = c("neutral_soft", surface_alt)

    btn_secondary_bg       = c("btn_secondary_bg", surface)
    btn_secondary_hover    = c("btn_secondary_hover", surface_alt)
    btn_secondary_pressed  = c("btn_secondary_pressed", divider)
    btn_secondary_border   = c("btn_secondary_border", border)
    btn_disabled_bg        = c("btn_disabled_bg", divider)
    btn_disabled_text      = c("btn_disabled_text", text_disabled)

    topbar_bg        = c("topbar_bg", surface)
    topbar_border    = c("topbar_border", border)
    search_bg        = c("search_bg", surface_alt)
    search_border    = c("search_border", border)

    nav_bg           = c("nav_bg", "#EEF2F7")
    nav_item         = c("nav_item", "#64748B")
    nav_item_hover   = c("nav_item_hover", "#E2E8F0")
    nav_item_sel     = c("nav_item_sel", "#DBEAFE")
    nav_item_sel_text= c("nav_item_sel_text", "#1E40AF")
    nav_brand        = c("nav_brand", "#172033")

    # ---- icons (theme coloured, file based) ----
    arrow_down = _icon("chevron_down", text_secondary)
    arrow_up   = _icon("chevron_up", text_secondary)
    check_icon = _icon("check", text_on_primary)

    return f"""
* {{
    font-family: {fam};
    font-size: {body_size}px;
    color: {text};
}}

QMainWindow, QDialog {{
    background-color: {bg};
}}

QWidget {{
    background-color: transparent;
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QSplitter::handle {{
    background-color: {divider};
}}

/* ==================== Menus ==================== */
QMenu {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: {RADIUS['sm']}px;
    padding: 6px;
}}

QMenu::item {{
    background-color: transparent;
    color: {text};
    padding: 8px 24px 8px 16px;
    border-radius: {RADIUS['xs']}px;
    margin: 1px 2px;
}}

QMenu::item:selected {{
    background-color: {primary_soft};
    color: {text};
}}

QMenu::item:disabled {{
    color: {text_disabled};
}}

QMenu::separator {{
    height: 1px;
    background-color: {divider};
    margin: 6px 8px;
}}

/* ==================== Top bar ==================== */
QWidget#topBar {{
    background-color: {topbar_bg};
    border-bottom: 1px solid {topbar_border};
}}

QWidget#topBar QLabel {{
    color: {text};
    background-color: transparent;
}}

QLabel#topBarTitle {{
    color: {text};
    background-color: transparent;
    font-size: 15px;
    font-weight: 600;
}}

QWidget#topBar QLineEdit {{
    background-color: {search_bg};
    border: 1px solid {search_border};
    border-radius: {RADIUS['md']}px;
    padding: 6px 12px;
    color: {text};
    min-height: 24px;
    font-size: 13px;
}}

QWidget#topBar QLineEdit:focus {{
    background-color: {surface};
    border: 1px solid {primary};
}}

/* ==================== Sidebar ==================== */
QWidget#sidebar {{
    background-color: {nav_bg};
}}

QListWidget#navList {{
    background-color: {nav_bg};
    border: none;
    border-radius: 0px;
    padding: 8px 6px;
    outline: none;
}}

QListWidget#navList::item {{
    color: {nav_item};
    padding: 10px 14px;
    border-radius: {RADIUS['md']}px;
    border: none;
    margin: 2px 4px;
    font-weight: 500;
    font-size: 14px;
}}

QListWidget#navList::item:hover:!selected {{
    background-color: {nav_item_hover};
    color: {nav_brand};
}}

QListWidget#navList::item:selected {{
    background-color: {nav_item_sel};
    color: {nav_item_sel_text};
    font-weight: 600;
}}

/* ==================== Workspace ==================== */
QWidget#workspace {{
    background-color: {bg};
}}

/* ==================== Group boxes ==================== */
QGroupBox {{
    font-weight: 600;
    font-size: {label_size + 1}px;
    color: {text_secondary};
    border: 1px solid {border};
    border-radius: {card_r}px;
    margin-top: 16px;
    padding: 18px 14px 14px 14px;
    background-color: {surface};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {text_secondary};
    background-color: {surface};
}}

/* ==================== Labels ==================== */
QLabel {{
    background-color: transparent;
    color: {text};
}}

QLabel[cssClass="muted"] {{
    color: {text_secondary};
}}

QLabel[cssClass="caption"] {{
    color: {text_secondary};
    font-size: {label_size}px;
}}

QLabel[cssClass="title"] {{
    color: {text};
    font-size: 18px;
    font-weight: 700;
}}

/* ==================== Buttons ==================== */
QPushButton {{
    background-color: {primary};
    color: {text_on_primary};
    border: none;
    border-radius: {btn_r}px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: {button_size}px;
    min-height: 22px;
}}

QPushButton:hover   {{ background-color: {primary_hover}; }}
QPushButton:pressed {{ background-color: {primary_pressed}; }}
QPushButton:focus   {{ outline: none; }}

QPushButton:disabled {{
    background-color: {btn_disabled_bg};
    color: {btn_disabled_text};
}}

QPushButton[cssClass="success"] {{
    background-color: {success};
    color: {text_on_primary};
}}
QPushButton[cssClass="success"]:hover   {{ background-color: {success_hover}; }}
QPushButton[cssClass="success"]:pressed {{ background-color: {success_pressed}; }}
QPushButton[cssClass="success"]:disabled {{
    background-color: {btn_disabled_bg};
    color: {btn_disabled_text};
}}

QPushButton[cssClass="warning"] {{
    background-color: {warning};
    color: {text_on_primary};
}}
QPushButton[cssClass="warning"]:hover   {{ background-color: {warning_hover}; }}
QPushButton[cssClass="warning"]:pressed {{ background-color: {warning_pressed}; }}
QPushButton[cssClass="warning"]:disabled {{
    background-color: {btn_disabled_bg};
    color: {btn_disabled_text};
}}

QPushButton[cssClass="danger"] {{
    background-color: {danger};
    color: {text_on_primary};
}}
QPushButton[cssClass="danger"]:hover   {{ background-color: {danger_hover}; }}
QPushButton[cssClass="danger"]:pressed {{ background-color: {danger_pressed}; }}
QPushButton[cssClass="danger"]:disabled {{
    background-color: {btn_disabled_bg};
    color: {btn_disabled_text};
}}

QPushButton[cssClass="secondary"] {{
    background-color: {btn_secondary_bg};
    color: {text};
    border: 1px solid {btn_secondary_border};
}}
QPushButton[cssClass="secondary"]:hover   {{ background-color: {btn_secondary_hover}; }}
QPushButton[cssClass="secondary"]:pressed {{ background-color: {btn_secondary_pressed}; }}
QPushButton[cssClass="secondary"]:focus   {{ border: 1px solid {primary}; }}
QPushButton[cssClass="secondary"]:disabled {{
    background-color: {btn_disabled_bg};
    color: {btn_disabled_text};
    border: 1px solid {border};
}}

QPushButton[cssClass="ghost"] {{
    background-color: transparent;
    color: {text_secondary};
    border: none;
    padding: 6px 10px;
}}
QPushButton[cssClass="ghost"]:hover {{
    background-color: {btn_secondary_hover};
    color: {text};
}}
QPushButton[cssClass="ghost"]:disabled {{
    background-color: transparent;
    color: {btn_disabled_text};
}}

/* Segment / chip: checkable pill (activity tabs, quick filters).
   Usage: btn.setCheckable(True); make_segment(btn) */
QPushButton[cssClass="segment"] {{
    background-color: {surface};
    color: {text_secondary};
    border: 1px solid {border};
    border-radius: 16px;
    padding: 6px 16px;
    font-weight: 600;
    min-height: 20px;
}}
QPushButton[cssClass="segment"]:hover {{
    background-color: {btn_secondary_hover};
    color: {text};
}}
QPushButton[cssClass="segment"]:checked {{
    background-color: {primary_soft};
    color: {primary};
    border: 1px solid {primary};
}}
QPushButton[cssClass="segment"]:disabled {{
    background-color: {btn_disabled_bg};
    color: {btn_disabled_text};
    border: 1px solid {border};
}}

QToolButton {{
    background-color: transparent;
    color: {text};
    border: none;
    border-radius: {btn_r}px;
    padding: 6px;
}}
QToolButton:hover   {{ background-color: {btn_secondary_hover}; }}
QToolButton:pressed {{ background-color: {btn_secondary_pressed}; }}
QToolButton:checked {{ background-color: {primary_soft}; }}

/* ==================== Checkboxes & radios ==================== */
QCheckBox, QRadioButton {{
    color: {text};
    background-color: transparent;
    spacing: 8px;
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {text_disabled};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {border};
    border-radius: 4px;
    background-color: {surface};
}}
QCheckBox::indicator:hover {{
    border-color: {primary};
}}
QCheckBox::indicator:checked {{
    background-color: {primary};
    border-color: {primary};
    image: {check_icon};
}}
QCheckBox::indicator:checked:hover {{
    background-color: {primary_hover};
    border-color: {primary_hover};
}}
QCheckBox::indicator:disabled {{
    background-color: {surface_alt};
    border-color: {divider};
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {border};
    border-radius: 11px;
    background-color: {surface};
}}
QRadioButton::indicator:hover {{
    border-color: {primary};
}}
QRadioButton::indicator:checked {{
    border: 6px solid {primary};
    background-color: {surface};
}}
QRadioButton::indicator:disabled {{
    background-color: {surface_alt};
    border-color: {divider};
}}

/* ==================== Inputs ==================== */
QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit, QPlainTextEdit {{
    border: 1px solid {border};
    border-radius: {input_r}px;
    padding: 8px 12px;
    background-color: {surface};
    color: {text};
    selection-background-color: {primary};
    selection-color: {text_on_primary};
    min-height: 22px;
    font-size: {body_size}px;
}}

QLineEdit:hover, QComboBox:hover, QDateEdit:hover,
QDoubleSpinBox:hover, QSpinBox:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border: 1px solid {text_disabled};
}}

QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
QDoubleSpinBox:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {primary};
}}

QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled,
QDoubleSpinBox:disabled, QSpinBox:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {surface_alt};
    color: {text_disabled};
    border: 1px solid {divider};
}}

QLineEdit:read-only {{
    background-color: {surface_alt};
}}

/* Validation: widget.setProperty("invalid", True) then polish_widget(widget) */
QLineEdit[invalid="true"], QComboBox[invalid="true"], QDateEdit[invalid="true"],
QDoubleSpinBox[invalid="true"], QSpinBox[invalid="true"], QTextEdit[invalid="true"] {{
    border: 1px solid {danger};
}}

/* Search variant: widget.setProperty("cssClass", "search") */
QLineEdit[cssClass="search"] {{
    background-color: {search_bg};
    border: 1px solid {search_border};
    border-radius: {RADIUS['md']}px;
    padding: 8px 14px;
}}
QLineEdit[cssClass="search"]:hover {{
    border: 1px solid {text_disabled};
}}
QLineEdit[cssClass="search"]:focus {{
    background-color: {surface};
    border: 1px solid {primary};
}}

/* Symmetric horizontal padding so the combo works in RTL and LTR */
QComboBox {{
    padding: 8px 30px;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 30px;
    border: none;
    background-color: transparent;
}}

QComboBox::down-arrow {{
    image: {arrow_down};
    width: 16px;
    height: 16px;
}}

QComboBox QAbstractItemView {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: {input_r}px;
    selection-background-color: {primary_soft};
    selection-color: {text};
    padding: 4px;
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 4px 8px;
    border-radius: {RADIUS['xs']}px;
}}

/* ==================== Spin boxes & date edits ==================== */
QDateEdit::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 30px;
    border: none;
    background-color: transparent;
}}

QDateEdit::up-button, QSpinBox::up-button, QDoubleSpinBox::up-button,
QDateEdit::down-button, QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 20px;
    border: none;
    background-color: transparent;
}}

QDateEdit::up-arrow, QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: {arrow_up};
    width: 12px;
    height: 12px;
}}

QDateEdit::down-arrow, QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: {arrow_down};
    width: 12px;
    height: 12px;
}}

/* ==================== Tables (QTableWidget and QTableView) ==================== */
QTableView {{
    border: 1px solid {border};
    border-radius: {card_r}px;
    gridline-color: {divider};
    background-color: {surface};
    alternate-background-color: {surface_alt};
    selection-background-color: {primary_soft};
    selection-color: {text};
    outline: none;
    font-size: {table_size}px;
}}

QTableView::item {{
    padding: 10px 12px;
    border: none;
}}

QTableView::item:hover {{
    background-color: {neutral_soft};
}}

QTableView::item:selected {{
    background-color: {primary_soft};
    color: {text};
}}

QHeaderView::section {{
    background-color: {surface_alt};
    color: {text_secondary};
    padding: 10px;
    border: none;
    border-bottom: 1px solid {border};
    font-weight: 600;
    font-size: {label_size}px;
}}

QHeaderView::section:hover {{
    background-color: {btn_secondary_hover};
    color: {text};
}}

QTableCornerButton::section {{
    background-color: {surface_alt};
    border: none;
    border-bottom: 1px solid {border};
}}

/* ==================== Progress bars ====================
   Set bar.setProperty("state", "success" | "warning" | "danger") and
   polish_widget(bar). Use setTextVisible(False) for slim session bars. */
QProgressBar {{
    background-color: {divider};
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {primary};
    border-radius: 4px;
}}
QProgressBar[state="success"]::chunk {{ background-color: {success}; }}
QProgressBar[state="warning"]::chunk {{ background-color: {warning}; }}
QProgressBar[state="danger"]::chunk  {{ background-color: {danger}; }}

/* ==================== Tabs ==================== */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: {card_r}px;
    background-color: {surface};
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {text_secondary};
    padding: 10px 20px;
    border-bottom: 2px solid transparent;
    margin: 0px 2px;
    font-weight: 600;
    font-size: {body_size}px;
}}

QTabBar::tab:selected {{
    color: {primary};
    border-bottom: 2px solid {primary};
}}

QTabBar::tab:hover:!selected {{ color: {text}; }}

/* ==================== Lists ==================== */
QListWidget {{
    border: 1px solid {border};
    border-radius: {card_r}px;
    background-color: {surface};
    color: {text};
    outline: none;
    padding: 4px;
}}

QListWidget::item {{
    padding: 10px 10px;
    border-radius: {RADIUS['sm']}px;
    margin: 1px 2px;
    color: {text};
}}

QListWidget::item:hover {{
    background-color: {surface_alt};
}}

QListWidget::item:selected {{
    background-color: {primary_soft};
    color: {text};
}}

/* ==================== Scrollbars ==================== */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {border};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {text_secondary}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {border};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {text_secondary}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

/* ==================== Tooltips ==================== */
QToolTip {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: {RADIUS['sm']}px;
    padding: 6px 8px;
    font-size: {label_size}px;
}}

/* ==================== Message boxes ==================== */
QMessageBox {{
    background-color: {surface};
}}
QMessageBox QLabel {{
    color: {text};
    background-color: transparent;
}}
QMessageBox QPushButton {{
    min-width: 80px;
}}

/* ==================== Date picker popup ====================
   QCalendarWidget's day grid is itself a QTableView, so it must be
   explicitly shielded from the generic table rules above (item padding,
   hover, header padding) — those were clipping the day numbers. */
QCalendarWidget QWidget {{
    background-color: {surface};
    color: {text};
    alternate-background-color: {surface};
}}
QCalendarWidget QAbstractItemView:enabled {{
    background-color: {surface};
    color: {text};
    selection-background-color: {primary};
    selection-color: {text_on_primary};
    outline: none;
}}
QCalendarWidget QAbstractItemView:disabled {{
    color: {text_disabled};
}}
QCalendarWidget QTableView#qt_calendar_calendarview {{
    border: none;
    border-radius: 0px;
    background-color: {surface};
    alternate-background-color: {surface};
    selection-background-color: {primary};
    selection-color: {text_on_primary};
    outline: none;
    font-size: {body_size}px;
}}
QCalendarWidget QTableView#qt_calendar_calendarview::item {{
    padding: 0px;
    margin: 1px;
    border: none;
    border-radius: 6px;
}}
QCalendarWidget QTableView#qt_calendar_calendarview::item:hover {{
    background-color: {primary_soft};
}}
QCalendarWidget QTableView#qt_calendar_calendarview::item:selected {{
    background-color: {primary};
    color: {text_on_primary};
}}
QCalendarWidget QTableView#qt_calendar_calendarview::item:disabled {{
    color: {text_disabled};
}}
QCalendarWidget QTableView#qt_calendar_calendarview QHeaderView::section {{
    background-color: {surface_alt};
    color: {text_secondary};
    padding: 4px;
    border: none;
    border-bottom: 1px solid {divider};
    font-weight: 600;
    font-size: {label_size}px;
}}
QCalendarWidget QMenu {{
    background-color: {surface};
    color: {text};
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background-color: {primary};
    color: {text_on_primary};
}}
QCalendarWidget QToolButton {{
    background-color: transparent;
    color: {text_on_primary};
    border: none;
    border-radius: {RADIUS['xs']}px;
    padding: 4px 10px;
    font-weight: 600;
}}
QCalendarWidget QToolButton:hover {{
    background-color: {primary_hover};
}}
QCalendarWidget QToolButton:pressed {{
    background-color: {primary_pressed};
}}
QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
QCalendarWidget QSpinBox {{
    background-color: transparent;
    color: {text_on_primary};
    border: none;
    padding: 2px 6px;
    min-height: 0px;
    font-weight: 600;
    selection-background-color: {primary_hover};
    selection-color: {text_on_primary};
}}
QCalendarWidget QComboBox {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: {RADIUS['xs']}px;
    padding: 2px 6px;
    min-height: 0px;
}}
"""


# Legacy constant still used by main.py
APP_STYLESHEET = build_stylesheet("light")


# ---------------------------------------------------------------------------
# ThemeManager
# ---------------------------------------------------------------------------

_SETTINGS_ORG = "MembershipSystem"
_SETTINGS_APP = "theme"
_PALETTES = {"light": LIGHT, "dark": DARK}


class ThemeManager(QObject):
    theme_changed = Signal(str)

    def __init__(self):
        super().__init__()
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        saved = s.value("mode", "light")
        self._mode = saved if saved in _PALETTES else "light"
        self._listeners: list = []

    @property
    def mode(self) -> str:
        return self._mode

    def is_dark(self) -> bool:
        return self._mode == "dark"

    def palette(self) -> dict:
        return _PALETTES[self._mode]

    def color(self, token: str) -> str:
        try:
            return self.palette()[token]
        except KeyError:
            raise KeyError(f"Unknown theme token: {token!r}")

    def build_palette(self) -> QPalette:
        p = self.palette()
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(p["bg"]))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.Base, QColor(p["surface"]))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(p["surface_alt"]))
        pal.setColor(QPalette.ColorRole.Text, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.Button, QColor(p["surface"]))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(p["primary"]))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(p.get("text_on_primary", "#FFFFFF")))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(p["surface"]))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(p["text_secondary"]))
        pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,
                     QColor(p["text_disabled"]))
        pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,
                     QColor(p["text_disabled"]))
        return pal

    def set_mode(self, mode: str, app: Optional[QApplication] = None):
        if mode not in _PALETTES or mode == self._mode:
            return

        app = app or QApplication.instance()

        # Freeze repaints on every visible top-level window while we
        # re-style everything, so the switch happens in one visual
        # frame instead of component-by-component.
        tops = []
        if app is not None:
            tops = [w for w in app.topLevelWidgets() if w.isVisible()]
            for w in tops:
                try:
                    w.setUpdatesEnabled(False)
                except Exception:
                    pass

        self._mode = mode
        QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue("mode", mode)

        if app is not None:
            self.apply(app)

        self.theme_changed.emit(self._mode)
        for cb in list(self._listeners):
            try:
                cb(self._mode)
            except Exception:
                pass

        # Unfreeze and force a single repaint of every top-level.
        for w in tops:
            try:
                w.setUpdatesEnabled(True)
                w.update()
            except Exception:
                pass

    def toggle(self, app: Optional[QApplication] = None):
        self.set_mode("dark" if self._mode == "light" else "light", app=app)

    def apply(self, app: QApplication):
        """
        Apply the current theme.

        Setting the app palette + stylesheet is enough — Qt
        automatically re-polishes every widget on the next paint, and
        every theme-reactive widget re-registers via theme().on_change.
        Do NOT walk the widget tree manually: that forces a synchronous
        polish per widget and is what made theme switching take seconds.
        """
        app.setPalette(self.build_palette())
        app.setStyleSheet(build_stylesheet(self._mode))

    @staticmethod
    def _deep_repolish(widget):
        try:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        except Exception:
            pass
        for child in widget.findChildren(object):
            if not hasattr(child, "style"):
                continue
            try:
                child.style().unpolish(child)
                child.style().polish(child)
                child.update()
            except Exception:
                pass

    @staticmethod
    def _repaint_cached_controls(top):
        for gb in top.findChildren(QGroupBox):
            gb.update()
        for tw in top.findChildren(QTabWidget):
            tw.update()
            try:
                tw.tabBar().update()
            except Exception:
                pass
        for tbl in top.findChildren(QTableWidget):
            try:
                tbl.viewport().update()
                tbl.horizontalHeader().viewport().update()
                tbl.verticalHeader().viewport().update()
            except Exception:
                pass
        for hdr in top.findChildren(QHeaderView):
            try:
                hdr.viewport().update()
            except Exception:
                pass
        for w in top.findChildren(object):
            if not hasattr(w, "graphicsEffect"):
                continue
            try:
                if w.graphicsEffect() is not None:
                    w.update()
            except Exception:
                pass

    def on_change(self, callback: Callable[[str], None]):
        self._listeners.append(callback)
        return callback


_theme: Optional[ThemeManager] = None


def theme() -> ThemeManager:
    global _theme
    if _theme is None:
        _theme = ThemeManager()
    return _theme


# ---------------------------------------------------------------------------
# ThemedWidget
# ---------------------------------------------------------------------------

class ThemedWidget:
    def _init_theme(self):
        try:
            self.setPalette(theme().build_palette())
        except Exception:
            pass

        try:
            from qtpy.QtWidgets import QDialog
            if isinstance(self, QDialog):
                self.setStyleSheet(
                    f"QDialog {{ background-color: {theme().color('bg')}; }}"
                )
        except Exception:
            pass

        self.restyle()
        theme().on_change(self._on_theme_change)

        try:
            ThemeManager._deep_repolish(self)
            top = self.window() if hasattr(self, "window") else self
            if top is not None:
                top.update()
        except Exception:
            pass

    def _on_theme_change(self, _mode):
        try:
            from qtpy.QtWidgets import QDialog
            if isinstance(self, QDialog):
                self.setStyleSheet(
                    f"QDialog {{ background-color: {theme().color('bg')}; }}"
                )
        except Exception:
            pass
        try:
            self.restyle()
        except Exception:
            pass

    def restyle(self):
        pass


def register_themed(widget):
    try:
        widget.restyle()
    except Exception:
        pass

    def _on_change(_mode, w=widget):
        try:
            w.restyle()
        except Exception:
            pass

    theme().on_change(_on_change)


# ---------------------------------------------------------------------------
# Button helpers
# ---------------------------------------------------------------------------

def polish_widget(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def make_danger(button):
    button.setProperty("cssClass", "danger")
    polish_widget(button)


def make_warning(button):
    """Amber/warning styled button — for 'sensitive but reversible' actions."""
    button.setProperty("cssClass", "warning")
    polish_widget(button)


def make_success(button):
    """Green button — for confirming / positive actions (renew, collect, save)."""
    button.setProperty("cssClass", "success")
    polish_widget(button)


def make_secondary(button):
    button.setProperty("cssClass", "secondary")
    polish_widget(button)


def make_ghost(button):
    button.setProperty("cssClass", "ghost")
    polish_widget(button)


def make_segment(button):
    """
    Pill-style checkable button (activity tabs, quick-filter chips).
    Call button.setCheckable(True) yourself; group them in a QButtonGroup
    with setExclusive(True) for tab-like behaviour.
    """
    button.setProperty("cssClass", "segment")
    polish_widget(button)


def set_progress_state(bar, state: Optional[str]):
    """
    Colour a QProgressBar chunk: 'success' | 'warning' | 'danger' | None
    (None = primary blue). Safe to call repeatedly.
    """
    bar.setProperty("state", state or "")
    polish_widget(bar)


# ---------------------------------------------------------------------------
# Toggle buttons
# ---------------------------------------------------------------------------

def theme_toggle_button() -> QPushButton:
    btn = QPushButton()
    btn.setObjectName("themeToggle")
    make_secondary(btn)
    _refresh_toggle_label(btn)

    def _on_click():
        theme().toggle()
        _refresh_toggle_label(btn)

    btn.clicked.connect(_on_click)
    theme().on_change(lambda _m: _refresh_toggle_label(btn))
    return btn


def _refresh_toggle_label(btn):
    try:
        from ui.i18n import t
        if theme().is_dark():
            btn.setText("☀   " + t("theme.light_mode"))
            btn.setToolTip(t("theme.switch_to_light"))
        else:
            btn.setText("☾   " + t("theme.dark_mode"))
            btn.setToolTip(t("theme.switch_to_dark"))
    except Exception:
        btn.setText("☾   Dark Mode" if not theme().is_dark() else "☀   Light Mode")


def language_toggle_button() -> QPushButton:
    from ui import i18n

    btn = QPushButton()
    btn.setObjectName("languageToggle")
    make_secondary(btn)

    def _refresh_label():
        if i18n.current_language() == "ar":
            btn.setText("🌐   English")
            btn.setToolTip("Switch to English")
        else:
            btn.setText("🌐   العربية")
            btn.setToolTip("Switch to Arabic")

    _refresh_label()

    def _on_click():
        from ui.main_window import request_language_change
        request_language_change()

    btn.clicked.connect(_on_click)
    return btn


# ---------------------------------------------------------------------------
# Fade helper (kept for compat)
# ---------------------------------------------------------------------------

def fade_in(widget: QWidget, duration_ms: int = 180):
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    widget._fade_anim = anim
    anim.start()


def force_repaint(widget):
    try:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    except Exception:
        pass
    widget.update()
    for child in widget.findChildren(object):
        if not hasattr(child, "style"):
            continue
        try:
            child.style().unpolish(child)
            child.style().polish(child)
            child.update()
        except Exception:
            pass