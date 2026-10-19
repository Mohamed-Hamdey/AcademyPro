"""
Design tokens — the single source of truth for every visual constant
in the app.

Nothing in the app should hardcode a hex color, a pixel value, or a
font size. Instead, ask `tokens` for it:

    from ui.design import tokens

    tokens.color("primary")        # → "#2563EB" (light) / "#60A5FA" (dark)
    tokens.space("lg")             # → 16
    tokens.radius("lg")          # → 12
    tokens.font_family()           # → "Segoe UI Variable"

The `tokens.color()` function reads the current theme mode via
ui.theme.theme().mode — design.py never imports theme directly, so
there's no circular dependency. It looks up the mode at call time.
"""

from __future__ import annotations


# ===========================================================================
# COLOR PALETTES
# ===========================================================================

# Light theme — exact values from the design brief, section 2.
LIGHT = {
    # Surfaces
    "bg":               "#F5F7FA",
    "surface":          "#FFFFFF",
    "surface_alt":      "#F8FAFC",
    "sidebar":          "#EEF2F7",
    "topbar":           "#FFFFFF",

    # Brand
    "primary":          "#2563EB",
    "primary_hover":    "#1D4ED8",
    "primary_pressed":  "#1E40AF",
    "primary_soft":     "#DBEAFE",

    # Text
    "text":             "#172033",
    "text_secondary":   "#64748B",
    "text_disabled":    "#94A3B8",
    "text_on_primary":  "#FFFFFF",
    "text_on_dark":     "#F3F4F6",

    # Structure
    "border":           "#DCE3EC",
    "divider":          "#E8EDF3",

    # Semantic
    "success":          "#16A34A",
    "success_soft":     "#DCFCE7",
    "warning":          "#D97706",
    "warning_soft":     "#FEF3C7",
    "warning_hover":    "#B45309",
    "warning_pressed":  "#92400E",
    "error":            "#DC2626",
    "error_soft":       "#FEE2E2",
    "info":             "#2563EB",
    "info_soft":        "#DBEAFE",
    "neutral":          "#64748B",
    "neutral_soft":     "#F1F5F9",

    # Destructive
    "danger":           "#DC2626",
    "danger_hover":     "#B91C1C",
    "danger_pressed":   "#991B1B",
    "danger_soft":      "#FEE2E2",

    # Buttons
    "btn_secondary_bg":       "#FFFFFF",
    "btn_secondary_hover":    "#F1F5F9",
    "btn_secondary_pressed":  "#E2E8F0",
    "btn_secondary_border":   "#DCE3EC",
    "btn_disabled_bg":        "#E2E8F0",
    "btn_disabled_text":      "#94A3B8",

    # Sidebar
    "nav_bg":           "#EEF2F7",
    "nav_brand":        "#172033",
    "nav_item":         "#64748B",
    "nav_item_hover":   "#E2E8F0",
    "nav_item_sel":     "#DBEAFE",
    "nav_item_sel_text":"#1E40AF",
    "nav_hairline":     "#DCE3EC",

    # Top bar
    "topbar_bg":        "#FFFFFF",
    "topbar_border":    "#DCE3EC",
    "search_bg":        "#F1F5F9",
    "search_border":    "#E2E8F0",

    # Shadow
    "shadow":           "#0F172A0F",

    # ---- Legacy aliases (v1 token names, kept so old screens keep working) ----
    "muted":            "#64748B",
    "surface_hover":    "#F1F5F9",
    "surface_pressed":  "#E2E8F0",
    "text_primary":     "#172033",
    "text_on_accent":   "#FFFFFF",
}

# Dark theme — from the design brief, section 2.
DARK = {
    # Surfaces
    "bg":               "#111827",
    "surface":          "#1F2937",
    "surface_alt":      "#273244",
    "sidebar":          "#151E2D",
    "topbar":           "#1A2434",

    # Brand
    "primary":          "#60A5FA",
    "primary_hover":    "#7CB1FB",
    "primary_pressed":  "#93C5FD",
    "primary_soft":     "#1E3A5F",

    # Text
    "text":             "#F3F4F6",
    "text_secondary":   "#9CA3AF",
    "text_disabled":    "#4B5563",
    "text_on_primary":  "#0B1220",
    "text_on_dark":     "#F3F4F6",

    # Structure
    "border":           "#374151",
    "divider":          "#2B3543",

    # Semantic
    "success":          "#4ADE80",
    "success_soft":     "#14532D",
    "warning":          "#FBBF24",
    "warning_soft":     "#78350F",
    "warning_hover":    "#FCD34D",
    "warning_pressed":  "#FDE68A",
    "error":            "#F87171",
    "error_soft":       "#7F1D1D",
    "info":             "#60A5FA",
    "info_soft":        "#1E3A5F",
    "neutral":          "#9CA3AF",
    "neutral_soft":     "#283344",

    # Destructive
    "danger":           "#F87171",
    "danger_hover":     "#FCA5A5",
    "danger_pressed":   "#FECACA",
    "danger_soft":      "#7F1D1D",

    # Buttons
    "btn_secondary_bg":       "#273244",
    "btn_secondary_hover":    "#31405A",
    "btn_secondary_pressed":  "#3B4B66",
    "btn_secondary_border":   "#374151",
    "btn_disabled_bg":        "#2B3543",
    "btn_disabled_text":      "#4B5563",

    # Sidebar
    "nav_bg":           "#151E2D",
    "nav_brand":        "#F3F4F6",
    "nav_item":         "#9CA3AF",
    "nav_item_hover":   "#1F2937",
    "nav_item_sel":     "#1E3A5F",
    "nav_item_sel_text":"#93C5FD",
    "nav_hairline":     "#1F2937",

    # Top bar
    "topbar_bg":        "#1A2434",
    "topbar_border":    "#374151",
    "search_bg":        "#273244",
    "search_border":    "#374151",

    # Shadow
    "shadow":           "#00000000",

    # ---- Legacy aliases (v1 token names, kept so old screens keep working) ----
    "muted":            "#9CA3AF",
    "surface_hover":    "#31405A",
    "surface_pressed":  "#3B4B66",
    "text_primary":     "#F3F4F6",
    "text_on_accent":   "#0B1220",

}


# ===========================================================================
# SPACING SCALE — 4px base (design brief section 5)
# ===========================================================================

SPACING = {
    "xs":  4,    # icon gaps, micro
    "sm":  8,    # compact
    "md":  12,   # form and component spacing
    "lg":  16,   # standard padding
    "xl":  24,   # card and section spacing
    "2xl": 32,   # major section separation
}
# ===========================================================================
# SHELL DIMENSIONS
# ===========================================================================

SHELL = {
    "topbar_height":  56,    # px
    "sidebar_width":  220,   # px
    "sidebar_collapsed_width": 67,
    "content_gutter": 24,    # px around workspace content
}


# ===========================================================================
# CORNER RADII (design brief section 5)
# ===========================================================================

RADIUS = {
    "xs":    4,    # compact controls
    "sm":    6,    # inputs, small buttons
    "md":    8,    # standard buttons and cards
    "lg":    12,   # larger panels and dialogs
}


# ===========================================================================
# TYPOGRAPHY (design brief section 3)
# ===========================================================================

TYPOGRAPHY = {
    # Page titles: 26–30 px, semibold
    "page_title":      {"size": 28, "weight": 600},
    # Section headings: 18–20 px, semibold
    "section":         {"size": 19, "weight": 600},
    # Card headings: 15–16 px, semibold
    "card_title":      {"size": 15, "weight": 600},
    # Body: 14 px, regular
    "body":            {"size": 14, "weight": 400},
    # Table content: 13–14 px
    "table":           {"size": 13, "weight": 400},
    # Labels and metadata: 12 px
    "label":           {"size": 12, "weight": 500},
    "meta":            {"size": 12, "weight": 400},
    # Buttons: 14 px, semibold
    "button":          {"size": 14, "weight": 600},
}

# Line-height multiplier (applied as line-height in QSS)
LINE_HEIGHT = 1.45


# ===========================================================================
# PUBLIC API — access tokens without importing the palettes directly
# ===========================================================================

class _Tokens:
    """
    Lookup helper. Reads the current theme mode at call time, so tokens
    automatically follow theme switches without any re-registration.
    """

    def color(self, name: str) -> str:
        """Return the current-mode hex value for a semantic color token."""
        from ui.theme import theme as _get_theme  # lazy to avoid cycle
        mode = _get_theme().mode  # "light" or "dark"
        palette = LIGHT if mode == "light" else DARK
        if name not in palette:
            raise KeyError(f"Unknown color token: {name!r}")
        return palette[name]

    def space(self, name: str) -> int:
        return SPACING[name]

    def radius(self, name: str) -> int:
        return RADIUS[name]

    def font_size(self, name: str) -> int:
        return TYPOGRAPHY[name]["size"]

    def font_weight(self, name: str) -> int:
        return TYPOGRAPHY[name]["weight"]

    def font_family(self) -> str:
        """
        Segoe UI Variable is the primary, with Segoe UI as Windows fallback.
        Qt's font-family CSS accepts a comma-separated list.
        """
        return "Segoe UI Variable, Segoe UI, Tahoma, sans-serif"


tokens = _Tokens()