"""
Themed replacements for QMessageBox.

On Windows, QMessageBox is drawn by the OS using the system theme, which
ignores the app QSS. That means in dark mode it looks fine, but in light
mode it stays dark — the exact bug we're fixing here.

These dialogs subclass ThemedWidget, so they follow the app's current
mode automatically. Same API as the QMessageBox calls they replace:

    from ui.message_box import info, warn, error, ask

    info(self, "Saved", "QR saved to:\n" + path)
    warn(self, "Cannot undo", "Only same-day check-ins...")
    error(self, "Save failed", str(e))
    if ask(self, title, body):
        ...
"""

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from qtpy.QtCore import Qt

from ui.theme import theme, ThemedWidget, make_secondary, make_danger
from ui.i18n import t


class MessageDialog(ThemedWidget, QDialog):
    """
    Themed dialog with an icon, a bold title, a body, and 1-2 buttons.

    Kinds:
      - "info":   one OK button
      - "warn":   one OK button (amber icon)
      - "error":  one OK button (red icon)
      - "ask":    Yes/No buttons; .confirmed is True if user clicked Yes
    """

    def __init__(self, parent, title, body, kind="info",
                 yes_label=None, no_label=None):
        QDialog.__init__(self, parent)
        self.kind = kind
        self.confirmed = False

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)

        self._build_ui(title, body, kind, yes_label, no_label)
        self._init_theme()

    def _build_ui(self, title, body, kind, yes_label, no_label):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(14)

        # --- header row: icon + title ---
        header = QHBoxLayout()
        header.setSpacing(12)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(36, 36)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.icon_label)

        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        header.addWidget(self.title_label, stretch=1)
        layout.addLayout(header)

        # --- body ---
        self.body_label = QLabel(body)
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.body_label)

        # --- buttons ---
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addStretch()

        if kind == "ask":
            self.no_button = QPushButton(no_label or t("msg.no") or "No")
            make_secondary(self.no_button)
            self.no_button.clicked.connect(self.reject)
            button_row.addWidget(self.no_button)

            self.yes_button = QPushButton(yes_label or t("msg.yes") or "Yes")
            self.yes_button.setDefault(True)
            self.yes_button.clicked.connect(self._on_yes)
            button_row.addWidget(self.yes_button)
        else:
            self.ok_button = QPushButton(t("msg.ok") or "OK")
            self.ok_button.setDefault(True)
            self.ok_button.clicked.connect(self.accept)
            button_row.addWidget(self.ok_button)

        layout.addLayout(button_row)

    def _on_yes(self):
        self.confirmed = True
        self.accept()

    def restyle(self):
        t_ = theme()

        # Icon glyph + accent per kind
        if self.kind == "info":
            glyph, color = "ℹ", t_.color("primary")
            bg = t_.color("primary_soft")
        elif self.kind == "warn":
            glyph, color = "⚠", t_.color("warning")
            bg = t_.color("warning_soft")
        elif self.kind == "error":
            glyph, color = "✕", t_.color("danger")
            bg = t_.color("danger_soft")
        else:  # ask
            glyph, color = "?", t_.color("primary")
            bg = t_.color("primary_soft")

        self.icon_label.setText(glyph)
        self.icon_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {color};"
            f"  background-color: {bg};"
            f"  border-radius: 18px;"
            f"  font-size: 18px;"
            f"  font-weight: 700;"
            f"}}"
        )
        self.title_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {t_.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 16px;"
            f"  font-weight: 700;"
            f"}}"
        )
        self.body_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {t_.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 13px;"
            f"}}"
        )


# ---------------------------------------------------------------------------
# Public helpers — drop-in for QMessageBox.<x>
# ---------------------------------------------------------------------------

def info(parent, title, body):
    """Like QMessageBox.information(parent, title, body)."""
    dlg = MessageDialog(parent, title, body, kind="info")
    dlg.exec()


def warn(parent, title, body):
    """Like QMessageBox.warning(parent, title, body)."""
    dlg = MessageDialog(parent, title, body, kind="warn")
    dlg.exec()


def error(parent, title, body):
    """Like QMessageBox.critical(parent, title, body)."""
    dlg = MessageDialog(parent, title, body, kind="error")
    dlg.exec()


def ask(parent, title, body, yes_label=None, no_label=None) -> bool:
    """
    Like QMessageBox.question(parent, title, body) but returns True/False
    instead of a StandardButton.
    """
    dlg = MessageDialog(parent, title, body, kind="ask",
                        yes_label=yes_label, no_label=no_label)
    dlg.exec()
    return dlg.confirmed