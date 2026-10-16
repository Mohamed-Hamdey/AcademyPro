"""
Global app theme (v4.1) — driven by ui/design.py tokens.

Fixes from v4.0:
  * build_stylesheet now includes a defensive `_safe()` helper so a
    missing token doesn't crash the whole QSS build.
  * Explicit high-specificity rules for top bar / sidebar text so
    nothing falls through to a wrong color.
"""

from __future__ import annotations

from typing import Callable, Optional

from qtpy.QtCore import QObject, QSettings, Signal, QEasingCurve, QPropertyAnimation
from qtpy.QtGui import QPalette, QColor
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
# Stylesheet builder
# ---------------------------------------------------------------------------

def _safe(palette: dict, key: str, fallback: str) -> str:
    """Return palette[key] or fallback if the token isn't defined."""
    return palette.get(key, fallback)


def build_stylesheet(mode: str) -> str:
    p = LIGHT if mode == "light" else DARK

    # Guard against accidentally-missing tokens by pre-resolving everything
    # through _safe(). If a token is missing, we fall back to a light-mode
    # default rather than crashing.
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

    # Pre-resolve every token we use
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
    primary_hover    = c("primary_hover", "#1D4ED8")
    primary_pressed  = c("primary_pressed", "#1E40AF")
    primary_soft     = c("primary_soft", "#DBEAFE")

    danger           = c("danger", "#DC2626")
    danger_hover     = c("danger_hover", "#B91C1C")
    danger_pressed   = c("danger_pressed", "#991B1B")

    btn_secondary_bg       = c("btn_secondary_bg", surface)
    btn_secondary_hover    = c("btn_secondary_hover", "#F1F5F9")
    btn_secondary_pressed  = c("btn_secondary_pressed", "#E2E8F0")
    btn_secondary_border   = c("btn_secondary_border", border)
    btn_disabled_bg        = c("btn_disabled_bg", "#E2E8F0")
    btn_disabled_text      = c("btn_disabled_text", "#94A3B8")

    topbar_bg        = c("topbar_bg", surface)
    topbar_border    = c("topbar_border", border)
    search_bg        = c("search_bg", "#F1F5F9")
    search_border    = c("search_border", "#E2E8F0")

    nav_bg           = c("nav_bg", "#EEF2F7")
    nav_item         = c("nav_item", "#64748B")
    nav_item_hover   = c("nav_item_hover", "#E2E8F0")
    nav_item_sel     = c("nav_item_sel", "#DBEAFE")
    nav_item_sel_text= c("nav_item_sel_text", "#1E40AF")
    nav_brand        = c("nav_brand", "#172033")
    nav_hairline     = c("nav_hairline", "#DCE3EC")

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
/* ==================== Menus (QMenu, popup menus) ==================== */
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

QLabel {{
    background-color: transparent;
    color: {text};
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

/* ==================== Inputs ==================== */
QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit {{
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

QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
QDoubleSpinBox:focus, QSpinBox:focus, QTextEdit:focus {{
    border: 1px solid {primary};
}}

QLineEdit::placeholder {{ color: {text_secondary}; }}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border-left: 1px solid {border};
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {text_secondary};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: {input_r}px;
    selection-background-color: {primary_soft};
    selection-color: {text};
    padding: 4px;
}}

/* ==================== Tables ==================== */
QTableWidget {{
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

QTableWidget::item {{
    padding: 10px 12px;
    border: none;
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
    margin-right: 4px;
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

/* ==================== Tooltips ==================== */
QToolTip {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: {RADIUS['sm']}px;
    padding: 6px 8px;
    font-size: {label_size}px;
}}

/* ==================== Date picker popup ==================== */
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
    padding: 4px 10px;
    font-weight: 600;
}}
QCalendarWidget QToolButton:hover {{
    background-color: {primary_hover};
    border-radius: {RADIUS['xs']}px;
}}
QCalendarWidget QToolButton:pressed {{
    background-color: {primary_pressed};
    border-radius: {RADIUS['xs']}px;
}}
QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
QCalendarWidget QComboBox {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: {RADIUS['xs']}px;
    padding: 2px 6px;
}}
QCalendarWidget QTableView QHeaderView::section {{
    background-color: {surface_alt};
    color: {text_secondary};
    padding: 4px;
    border: none;
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
# Sweep
# ---------------------------------------------------------------------------

def sweep_restyle():
    app = QApplication.instance()
    if app is None:
        return
    seen = set()
    for top in app.topLevelWidgets():
        _maybe_restyle(top, seen)
        for w in top.findChildren(object):
            _maybe_restyle(w, seen)


def _maybe_restyle(widget, seen):
    if id(widget) in seen:
        return
    seen.add(id(widget))
    fn = getattr(widget, "restyle", None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


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


def make_secondary(button):
    button.setProperty("cssClass", "secondary")
    polish_widget(button)


def make_ghost(button):
    button.setProperty("cssClass", "ghost")
    polish_widget(button)


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