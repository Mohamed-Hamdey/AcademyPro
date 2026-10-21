"""
Shared helpers for the v5-style dialogs.

Save as ui/form_helpers.py. Used by the championship dialog; the user dialog
currently carries its own copy of the same helpers and can switch to this module
later (optional cleanup — nothing breaks if you leave it).
"""

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QWidget, QLabel, QHBoxLayout, QFrame

from ui import i18n
from ui.i18n import t
from ui.theme import theme


def col(name: str, fallback_token: str, default: str) -> QColor:
    """Resolve a theme colour without ever raising."""
    try:
        pal = theme().palette()
        return QColor(pal.get(name) or pal.get(fallback_token) or default)
    except Exception:
        return QColor(default)


def hex_(name: str, fallback_token: str, default: str) -> str:
    return col(name, fallback_token, default).name()


def tr(key: str, ar: str, en: str) -> str:
    """t(key), but fall back to a built-in string while the key is missing."""
    text = t(key)
    if text == key:
        return ar if i18n.current_language() == "ar" else en
    return text


class FieldLabel(QWidget):
    """
    Form label with an optional separate red asterisk.

    The asterisk is its own QLabel instead of a "*" glued onto the translated
    text: a trailing "*" in an Arabic string is bidi-neutral, jumps to the wrong
    side and collides with the last letter. Two widgets in a layout are mirrored
    correctly by Qt in RTL (text at the start, asterisk right after it).
    Any "*" already present at the end of the translation is stripped.
    """

    def __init__(self, text: str, required: bool = False, parent=None):
        QWidget.__init__(self, parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        self.text_lbl = QLabel((text or "").rstrip(" *"), self)
        lay.addWidget(self.text_lbl)

        self.star_lbl = None
        if required:
            self.star_lbl = QLabel("*", self)
            lay.addWidget(self.star_lbl)
        lay.addStretch(1)
        self.apply_theme()

    def apply_theme(self):
        if self.star_lbl is not None:
            self.star_lbl.setStyleSheet(
                f"QLabel {{ color: {hex_('danger', 'danger', '#DC2626')};"
                f" font-weight: 700; background: transparent; }}"
            )


def make_divider(parent=None, object_name: str = "formDivider") -> QFrame:
    line = QFrame(parent)
    line.setObjectName(object_name)
    line.setFixedHeight(1)
    style_divider(line)
    return line


def style_divider(line: QFrame):
    name = line.objectName() or "formDivider"
    line.setStyleSheet(
        f"QFrame#{name} {{ background-color: {hex_('divider', 'border', '#E8EDF3')};"
        f" border: none; }}"
    )