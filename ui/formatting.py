"""
Shared formatting helpers for attendance rows.

Extracted from scan_screen so the "Recent check-ins" panel and the full
"Today's log" dialog render rows identically.
"""


def is_ar() -> bool:
    from ui import i18n
    return i18n.current_language() == "ar"


def format_attendance_row(r: dict) -> str:
    """
    Compose the single-line string shown in the recent / full-log lists.

    Expected keys on `r`:
        result, was_override, time_only, player_name,
        activity_name_ar, activity_name_en,
        deny_reason, override_note
    """
    if r["result"] == "allowed":
        icon = "✓*" if r["was_override"] else "✓ "
    else:
        icon = "✕ "

    time_part = r.get("time_only") or ""
    name = r.get("player_name") or "?"

    act = ""
    if r.get("activity_name_ar") or r.get("activity_name_en"):
        act = (r["activity_name_ar"] if is_ar() else r["activity_name_en"]) or ""

    extra = ""
    if r["result"] == "denied" and r.get("deny_reason"):
        extra = r["deny_reason"]
    elif r["was_override"] and r.get("override_note"):
        extra = f"[{r['override_note']}]"

    parts = [icon, time_part, "  ", name]
    if act:
        parts += ["   ·   ", act]
    if extra:
        parts += ["   —   ", extra]
    return "".join(parts)