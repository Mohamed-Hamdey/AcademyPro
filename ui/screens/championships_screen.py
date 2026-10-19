"""
Championships Main Screen — Card List Layout.
"""
import os
import sys
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QFrame, QLineEdit,QStackedWidget
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import championships_repo
from ui.dialogs.championship_form_dialog import ChampionshipFormDialog
from ui.screens.championship_detail_screen import ChampionshipDetailScreen
from ui.theme import theme, ThemedWidget, make_danger, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.utils import Debouncer
from ui.components import Toolbar
from ui.message_box import ask

class ChampionshipCard(QFrame):
    def __init__(self, champ, on_click, parent=None):
        super().__init__(parent)
        self.setObjectName("champCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.champ = champ
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        icon = QLabel("🏆")
        icon.setStyleSheet("font-size: 32px;")
        layout.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(4)
        title = QLabel(champ.name)
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme().color('text')};")
        col.addWidget(title)
        
        sub = QLabel(f"{champ.event_date}  ·  {champ.location or '—'}")
        sub.setStyleSheet(f"font-size: 13px; color: {theme().color('text_secondary')};")
        col.addWidget(sub)
        
        layout.addLayout(col, stretch=1)
        self.mousePressEvent = lambda e: on_click(champ.championship_id)

class ChampionshipsScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        self.stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stack)

        # List Page
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["lg"])

        # Toolbar
        self.toolbar = Toolbar()
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("champ.search"))
        self.search.setProperty("cssClass", "search")
        self.search.setMinimumWidth(240)
        
        self.debouncer = Debouncer(250, self.refresh, parent=self)
        self.search.textChanged.connect(self.debouncer.trigger)

        self.add_btn = QPushButton(t("champ.add"))
        self.add_btn.clicked.connect(self._on_add)
        
        self.delete_btn = QPushButton(t("msg.delete"))
        make_danger(self.delete_btn)
        self.delete_btn.hide() # We'll do this from the detail screen

        self.toolbar.add_leading(self.search, stretch=1)
        self.toolbar.add_trailing(self.add_btn)
        layout.addWidget(self.toolbar)

        # Scroll area for cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(SPACING["md"])
        self.cards_layout.addStretch()
        
        self.scroll.setWidget(self.cards_widget)
        layout.addWidget(self.scroll, stretch=1)

        self.stack.addWidget(page)
        self.stack.setCurrentIndex(0)

    def restyle(self):
        tm = theme()
        self.setStyleSheet(f"QFrame#champCard {{ background: {tm.color('surface')}; border: 1px solid {tm.color('border')}; border-radius: {RADIUS['md']}px; }}")
        if self.stack.currentIndex() == 0:
            self.refresh()

    def refresh(self):
        # Clear cards
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
            
        champs = championships_repo.list_championships()
        query = self.search.text().strip().lower()
        if query:
            champs = [c for c in champs if query in c.name_en.lower() or query in c.name_ar.lower()]

        for c in champs:
            card = ChampionshipCard(c, self._open_detail)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _on_add(self):
        dlg = ChampionshipFormDialog(parent=self)
        if dlg.exec(): self.refresh()

    def _open_detail(self, champ_id):
        detail = ChampionshipDetailScreen(champ_id, on_back=self._close_detail, parent=self)
        self.stack.addWidget(detail)
        self.stack.setCurrentWidget(detail)

    def _close_detail(self):
        curr = self.stack.currentWidget()
        self.stack.setCurrentIndex(0)
        self.stack.removeWidget(curr)
        curr.deleteLater()
        self.refresh()