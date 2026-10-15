"""
Startup splash screen.

Builds a themed splash pixmap on the fly from the academy logo +
name, so there's no separate splash asset to maintain.

Usage in main.py:

    from ui.splash import show_splash, finish_splash
    splash = show_splash()
    # ... do slow startup work ...
    finish_splash(splash)
"""

import os

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import QSplashScreen

from paths import AppPaths


SPLASH_W = 500
SPLASH_H = 300
LOGO_SIZE = 180


def _build_splash_pixmap() -> QPixmap:
    """
    Compose a splash: academy logo centered on a soft surface, academy
    name underneath. Falls back to a text-only splash if the logo is
    missing.
    """
    # Read the current palette (light or dark) so the splash matches.
    # Import here to avoid a circular import at module load.
    from ui.theme import theme
    tm = theme()
    bg = QColor(tm.color("surface"))
    fg = QColor(tm.color("text"))
    accent = QColor(tm.color("primary"))

    pix = QPixmap(SPLASH_W, SPLASH_H)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # Rounded background
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(0, 0, SPLASH_W, SPLASH_H, 18, 18)

    # Thin accent border
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(accent)
    p.drawRoundedRect(1, 1, SPLASH_W - 2, SPLASH_H - 2, 18, 18)

    # Logo, centered horizontally, in the upper portion
    logo_path = AppPaths.logo_file()
    logo_drawn = False
    if os.path.exists(logo_path):
        src = QPixmap(logo_path)
        if not src.isNull():
            scaled = src.scaled(
                LOGO_SIZE, LOGO_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            lx = (SPLASH_W - scaled.width()) // 2
            ly = 30
            p.drawPixmap(lx, ly, scaled)
            logo_drawn = True

    # Academy name — under the logo, or centered if no logo.
    name = _academy_display_name()
    font = QFont()
    font.setPixelSize(22)
    font.setBold(True)
    p.setFont(font)
    p.setPen(fg)

    if logo_drawn:
        text_top = 30 + LOGO_SIZE + 20
    else:
        text_top = SPLASH_H // 2 - 20
    text_rect = QRect(20, text_top, SPLASH_W - 40, SPLASH_H - text_top - 20)
    p.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
        name,
    )

    # Small "loading" hint at the bottom
    hint_font = QFont()
    hint_font.setPixelSize(11)
    p.setFont(hint_font)
    p.setPen(QColor(tm.color("text_secondary")))
    p.drawText(
        QRect(0, SPLASH_H - 32, SPLASH_W, 24),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        "…",
    )

    p.end()
    return pix


def _academy_display_name() -> str:
    """Localized academy name from the config, with a safe fallback."""
    try:
        from config.config_loader import load_config
        from ui import i18n
        cfg = load_config()
        if i18n.current_language() == "ar":
            return cfg.get("academy_name_ar") or cfg.get("academy_name", "")
        return cfg.get("academy_name", "")
    except Exception:
        return "Academy"


def show_splash() -> QSplashScreen:
    """Create and show the splash. Returns the QSplashScreen object."""
    pix = _build_splash_pixmap()
    splash = QSplashScreen(pix)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    splash.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    splash.show()
    # Force an immediate paint so the splash is visible during the
    # first slow import.
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    return splash


def finish_splash(splash: QSplashScreen):
    """Hide the splash once the first real window is ready to show."""
    try:
        splash.finish(None)
        splash.close()
        splash.deleteLater()
    except Exception:
        pass