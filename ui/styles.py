"""
Named stylesheet helpers.

Every QSS block used in more than one place should live here as a
function. Screens call the function and get the string; if the design
changes, we edit one function, and all call sites update.

Conventions:
- Each function returns a string.
- Each function reads from `theme()` at call time, so switching themes
  changes the result automatically (as long as the caller re-calls).
- Names are `[color]_[component]` — e.g. `secondary_label`,
  `muted_small_label`, `card_surface`.
"""

from ui.theme import theme
from ui.design import RADIUS, TYPOGRAPHY


def _t():
    return theme()


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def primary_label() -> str:
    """Standard body-text label."""
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('text')};"
        f"  background-color: transparent;"
        f"  font-size: {TYPOGRAPHY['body']['size']}px;"
        f"}}"
    )


def secondary_label() -> str:
    """Dimmed label for secondary information."""
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('text_secondary')};"
        f"  background-color: transparent;"
        f"  font-size: {TYPOGRAPHY['body']['size']}px;"
        f"}}"
    )


def muted_label() -> str:
    """Small italic label for hints / empty messages."""
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('text_secondary')};"
        f"  background-color: transparent;"
        f"  font-style: italic;"
        f"  font-size: {TYPOGRAPHY['meta']['size']}px;"
        f"}}"
    )


def small_meta_label() -> str:
    """Very small secondary label for footnotes."""
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('text_secondary')};"
        f"  background-color: transparent;"
        f"  font-size: 11px;"
        f"}}"
    )


def bold_label() -> str:
    """Body-size label with bold weight."""
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('text')};"
        f"  background-color: transparent;"
        f"  font-size: {TYPOGRAPHY['body']['size']}px;"
        f"  font-weight: 600;"
        f"}}"
    )


def card_title_label() -> str:
    """Section-card title."""
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('text')};"
        f"  background-color: transparent;"
        f"  font-size: {TYPOGRAPHY['card_title']['size']}px;"
        f"  font-weight: 600;"
        f"}}"
    )


def card_subtitle_label() -> str:
    """Section-card subtitle."""
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('text_secondary')};"
        f"  background-color: transparent;"
        f"  font-size: {TYPOGRAPHY['meta']['size']}px;"
        f"}}"
    )


# ---------------------------------------------------------------------------
# Colors — semantic labels
# ---------------------------------------------------------------------------

def success_label() -> str:
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('success')};"
        f"  background-color: transparent;"
        f"  font-size: {TYPOGRAPHY['body']['size']}px;"
        f"  font-weight: 600;"
        f"}}"
    )


def danger_label() -> str:
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('danger')};"
        f"  background-color: transparent;"
        f"  font-size: {TYPOGRAPHY['body']['size']}px;"
        f"  font-weight: 600;"
        f"}}"
    )


def warning_label() -> str:
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('warning')};"
        f"  background-color: transparent;"
        f"  font-size: {TYPOGRAPHY['body']['size']}px;"
        f"  font-weight: 600;"
        f"}}"
    )


# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------

def card_surface() -> str:
    """Standard rounded card background."""
    t_ = _t()
    return (
        f"QFrame#sectionCard {{"
        f"  background-color: {t_.color('surface')};"
        f"  border: 1px solid {t_.color('border')};"
        f"  border-radius: {RADIUS['lg']}px;"
        f"}}"
    )
    
def week_hint_label() -> str:
    """Small dimmed hint above the 7-day table."""
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('text_secondary')};"
        f"  background-color: transparent;"
        f"  font-size: 12px;"
        f"  padding: 0 0 6px 0;"
        f"}}"
    )


def payments_total_label() -> str:
    """Bold total line below the payments table."""
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('text')};"
        f"  background-color: transparent;"
        f"  font-size: 14px;"
        f"  font-weight: 700;"
        f"  padding-top: 6px;"
        f"}}"
    )


def badge_label(color: str) -> str:
    """Small bold label with a dynamic color (used for KPI comparison badges)."""
    return (
        f"QLabel {{"
        f"  color: {color};"
        f"  background-color: transparent;"
        f"  font-size: 11px;"
        f"  font-weight: 600;"
        f"}}"
    )


def recon_label() -> str:
    """Reconciliation strip label."""
    t_ = _t()
    return (
        f"QLabel {{"
        f"  color: {t_.color('text')};"
        f"  background-color: transparent;"
        f"  font-size: 13px;"
        f"  padding: 4px 8px;"
        f"}}"
    )