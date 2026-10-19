"""
Championships Main Screen — Card List Layout.
"""
import os
import sys
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QFrame, QLineEdit, QStackedWidget,
)
from qtpy.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import championships_repo
from services import activity_service
from ui.dialogs.championship_form_dialog import ChampionshipFormDialog
from ui.screens.championship_detail_screen import ChampionshipDetailScreen
from ui.theme import theme, ThemedWidget, make_danger
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.utils import Debouncer
from ui.components import Toolbar
from logic.arabic_normalize import normalize_arabic


class ChampionshipCard(ThemedWidget, QFrame):
    """Card row for the championships list — theme-reactive."""

    def __init__(self, champ, on_click, parent=None):
        QFrame.__init__(self, parent)
        self.setObjectName("champCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.champ = champ
        self._on_click = on_click
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        self.icon = QLabel("🏆")
        self.icon.setStyleSheet("font-size: 32px;")
        layout.addWidget(self.icon)

        col = QVBoxLayout()
        col.setSpacing(4)

        self.title = QLabel(self.champ.name)
        col.addWidget(self.title)

        self.sub = QLabel(self._build_subtitle())
        col.addWidget(self.sub)

        layout.addLayout(col, stretch=1)

    def _build_subtitle(self) -> str:
        """Date · Activity · Location — the first two always, location if set."""
        parts = [self.champ.event_date or "—"]
        act = (activity_service.get(self.champ.activity_id)
               if self.champ.activity_id else None)
        if act is not None:
            parts.append(activity_service.get_localized_name(act))
        if self.champ.location:
            parts.append(self.champ.location)
        return "  ·  ".join(parts)

    def restyle(self):
        tm = theme()
        self.setStyleSheet(
            f"QFrame#champCard {{"
            f"  background: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['md']}px;"
            f"}}"
        )
        self.title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {tm.color('text')};"
        )
        self.sub.setStyleSheet(
            f"font-size: 13px; color: {tm.color('text_secondary')};"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self.champ.championship_id)
        super().mousePressEvent(event)


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

        # --- List page ---
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["lg"])

        self.toolbar = Toolbar()
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("champ.search"))
        self.search.setProperty("cssClass", "search")
        self.search.setMinimumWidth(240)

        self.debouncer = Debouncer(250, self.refresh, parent=self)
        self.search.textChanged.connect(self.debouncer.trigger)

        self.add_btn = QPushButton(t("champ.add"))
        self.add_btn.clicked.connect(self._on_add)

        self.toolbar.add_leading(self.search, stretch=1)
        self.toolbar.add_trailing(self.add_btn)
        layout.addWidget(self.toolbar)

        # --- Scroll area for cards ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(SPACING["md"])

        # Empty-state label — shown when no championships match.
        self.empty_label = QLabel(t("champ.empty"))
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()

        # Trailing stretch keeps cards top-aligned.
        self.cards_layout.addWidget(self.empty_label)
        self.cards_layout.addStretch()

        self.scroll.setWidget(self.cards_widget)
        layout.addWidget(self.scroll, stretch=1)

        self.stack.addWidget(page)
        self.stack.setCurrentIndex(0)

    def restyle(self):
        tm = theme()
        self.empty_label.setStyleSheet(
            f"QLabel {{ color: {tm.color('text_secondary')};"
            f"  font-style: italic; padding: 32px; }}"
        )
        # Card restyle is triggered by ThemedWidget machinery when the
        # theme changes — we just need to re-render the scroll area's
        # stylesheet so no stale border leaks through.
        self.cards_widget.setStyleSheet(
            f"QWidget {{ background: transparent; }}"
        )
        self.scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
        )

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def refresh(self):
        # Clear existing cards (invariant #2: setParent(None) BEFORE deleteLater)
        while self.cards_layout.count() > 2:            # keep empty_label + stretch
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w is not None and w is not self.empty_label:
                w.setParent(None)
                w.deleteLater()

        champs = championships_repo.list_championships()

        # Arabic-aware search across the single `name` field.
        query = self.search.text().strip()
        if query:
            norm_q = normalize_arabic(query).lower()
            champs = [
                c for c in champs
                if norm_q in normalize_arabic(c.name or "").lower()
            ]

        if not champs:
            self.empty_label.show()
            return

        self.empty_label.hide()

        # Insert before the stretch (which is always the last item).
        insert_pos = self.cards_layout.count() - 1
        for c in champs:
            card = ChampionshipCard(c, self._open_detail)
            self.cards_layout.insertWidget(insert_pos, card)
            insert_pos += 1

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_add(self):
        dlg = ChampionshipFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _open_detail(self, champ_id):
        detail = ChampionshipDetailScreen(
            champ_id, on_back=self._close_detail, parent=self
        )
        self.stack.addWidget(detail)
        self.stack.setCurrentWidget(detail)

    def _close_detail(self):
        curr = self.stack.currentWidget()
        self.stack.setCurrentIndex(0)
        self.stack.removeWidget(curr)
        curr.deleteLater()
        self.refresh()