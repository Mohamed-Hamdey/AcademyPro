"""
Arabic text normalization for search.

The problem: users type "احمد" but the stored name is "أحمد". Simple
LIKE queries miss these. Normalizing both sides fixes it.

This is a lightweight approach — no full-text indexing, no diacritics
for now. It handles the common substitutions:

    أ إ آ → ا
    ة     → ه
    ى     → ي
    ؤ     → و
    ئ     → ي
    Diacritics (tashkeel) → removed

Usage:

    from logic.arabic_normalize import normalize_arabic

    normalized = normalize_arabic("أحمد")   # "احمد"
"""

import re


# Common substitutions (single character → single character)
_CHAR_MAP = {
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ة": "ه",
    "ى": "ي",
    "ؤ": "و",
    "ئ": "ي",
}


# Diacritics range: U+064B..U+065F plus the superscript alef
_DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670]")


def normalize_arabic(text: str) -> str:
    """
    Normalize Arabic text for searching.

    Does not touch Latin characters, numbers, or other scripts —
    normalizes only the Arabic blocks. Safe to call on any string.
    """
    if not text:
        return ""
    # Remove diacritics
    text = _DIACRITICS_RE.sub("", text)
    # Character substitutions
    out = []
    for ch in text:
        out.append(_CHAR_MAP.get(ch, ch))
    return "".join(out)