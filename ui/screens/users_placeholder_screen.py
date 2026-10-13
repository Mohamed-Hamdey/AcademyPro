"""
Placeholder for the Users management screen.

Manager-only. Shows a "coming soon" empty state. Replaced with a real
screen in Batch 1.3.
"""

import os
import sys

from PyQt6.QtWidgets import QWidget, QVBoxLayout

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ui.components import EmptyState
from ui.design import SPACING


class UsersPlaceholderScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING["lg"], 0, 0)
        layout.addStretch()

        self.empty = EmptyState(
            icon="🚧",
            message="إدارة المستخدمين — قادمة في التحديث القادم.",
        )
        layout.addWidget(self.empty)
        layout.addStretch()