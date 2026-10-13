"""
Legacy widget names — thin aliases over ui.components.

v1 screens import `Card`, `StatusPill`, `StatCard`, `hairline` from this
module. Rather than rewrite every screen at once (Batch 0.4b does that
screen-by-screen), this module re-exports the new components under the
old names so nothing breaks.

Once all screens are ported to ui.components, this file can be deleted.
"""

from ui.components import (
    SectionCard, Toolbar, KpiCard, EmptyState, Pill, hairline,
    primary_button, secondary_button, ghost_button, danger_button,
)


# ---- Legacy aliases ----

class Card(SectionCard):
    """
    v1 Card — kept for backward compatibility.

    The v1 API exposed `card.body` (QVBoxLayout) and `card.set_title(...)`.
    SectionCard has both. The only incompatibility: v1's Card constructor
    took `title: str = ""` and that's still what we accept.

    Screens that did `card = Card("Camera")` and then
    `card.body.addWidget(x)` work unchanged.
    """

    def __init__(self, title: str = "", parent=None):
        super().__init__(title=title, parent=parent)


class StatusPill(Pill):
    """v1 name for Pill."""

    def __init__(self, text: str = "", kind: str = "neutral", parent=None):
        super().__init__(text=text, kind=kind, parent=parent)


class StatCard(KpiCard):
    """
    v1 name for KpiCard. v1's signature was:
        StatCard(caption, value, accent="primary")

    New signature is:
        KpiCard(title, value, subtitle="")

    The `accent` argument is accepted and ignored — accents are no longer
    a thing; the color scheme is uniform.
    """

    def __init__(self, caption: str, value: str = "0",
                 accent: str = "primary", parent=None):
        super().__init__(title=caption, value=value, subtitle="", parent=parent)