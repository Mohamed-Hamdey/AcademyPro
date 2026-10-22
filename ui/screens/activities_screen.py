"""
Activities management screen — v5 (Card layout with Detail view).
"""
import os
import sys
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QScrollArea, QFrame, QLabel, QStackedWidget, QButtonGroup
)
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import activity_service
from ui.components import Toolbar, EmptyState
from ui.theme import theme, ThemedWidget, make_segment
from ui.screens.activity_detail_screen import ActivityDetailScreen
from ui.dialogs.activity_form_dialog import ActivityFormDialog
from ui.theme import theme, ThemedWidget
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.utils import Debouncer


class ActivityCard(ThemedWidget, QFrame):
    """Compact row card for the activities list."""
    def __init__(self, act, on_click, parent=None):
        QFrame.__init__(self, parent)
        self.setObjectName("activityCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.act = act
        self._on_click = on_click
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Left: Color indicator (if any) + Name
        if self.act.color:
            color_strip = QFrame(self)
            color_strip.setFixedWidth(6)
            color_strip.setStyleSheet(f"background-color: {self.act.color}; border-radius: 3px;")
            layout.addWidget(color_strip)

        col1 = QVBoxLayout()
        col1.setSpacing(4)
        self.title = QLabel(self.act.name, self)
        
        days_str = ", ".join(t(f"weekday.{d.lower()}") for d in self.act.default_days)
        self.sub = QLabel(days_str or "—", self)
        
        col1.addWidget(self.title)
        col1.addWidget(self.sub)
        layout.addLayout(col1, stretch=1)

        # Right: Metrics (Active Players)
        col2 = QVBoxLayout()
        col2.setSpacing(4)
        col2.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        count = activity_service.count_active_references(self.act.activity_id)
        self.count_label = QLabel(t("activities.detail.kpi.players") + f": {count}", self)
        col2.addWidget(self.count_label)
        
        layout.addLayout(col2)

    def restyle(self):
        tm = theme()
        self.setStyleSheet(
            f"QFrame#activityCard {{"
            f"  background: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['md']}px;"
            f"}}"
            f"QFrame#activityCard:hover {{"
            f"  border: 1px solid {tm.color('primary')};"
            f"}}"
        )
        self.title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {tm.color('text')};")
        self.sub.setStyleSheet(f"font-size: 12px; color: {tm.color('text_secondary')};")
        self.count_label.setStyleSheet(f"font-size: 12px; color: {tm.color('text')}; font-weight: 600;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self.act.activity_id)
        super().mousePressEvent(event)


class ActivitiesScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._dirty = True
        self._build_ui()
        self._init_theme()

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self._dirty = False
            QTimer.singleShot(0, self.refresh)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._dirty = True

    def _build_ui(self):
        self.stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stack)

        # --- List page ---
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["md"])

        # Toolbar
        self.toolbar = Toolbar()
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("activities.search_placeholder"))
        self.search.setProperty("cssClass", "search")
        self.search.setMinimumWidth(200)
        self.debouncer = Debouncer(250, QTimer.singleShot(0, self.refresh), parent=self)
        self.search.textChanged.connect(self.debouncer.trigger)

        self.add_btn = QPushButton(t("activities.add"))
        self.add_btn.clicked.connect(self._on_add)

        self.toolbar.add_leading(self.search, stretch=1)
        self.toolbar.add_trailing(self.add_btn)
        layout.addWidget(self.toolbar)

        # Filter chips
        chips_row = QHBoxLayout()
        chips_container = QWidget(page)
        chips_row = QHBoxLayout(chips_container)
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(SPACING["sm"])
        
        self.chip_all = QPushButton(t("activities.filter.all"), chips_container)
        self.chip_active = QPushButton(t("activities.filter.active"), chips_container)
        self.chip_archived = QPushButton(t("activities.filter.archived"), chips_container)

        self._chips_group = QButtonGroup(self)
        self._chips_group.setExclusive(True)
        self._active_chip = self.chip_all

        for chip in (self.chip_all, self.chip_active, self.chip_archived):
            chip.setCheckable(True)
            make_segment(chip)
            self._chips_group.addButton(chip)
            chip.clicked.connect(lambda checked, c=chip: self._on_chip_clicked(c))
            chips_row.addWidget(chip)
        
        self.chip_all.setChecked(True)
        chips_row.addStretch()
        layout.addWidget(chips_container)

        # Scroll Area
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

        # Empty states
        self.empty_first_run = EmptyState(icon="🏃", message=t("activities.empty"), action_text=t("activities.add"), on_action=self._on_add)
        self.empty_no_results = EmptyState(icon="🔍", message=t("activities.no_results"))
        for empty in (self.empty_first_run, self.empty_no_results):
            empty.hide()
            layout.addWidget(empty, stretch=1)

        self.stack.addWidget(page)
        self.stack.setCurrentIndex(0)

    def restyle(self):
        pass

    def _on_chip_clicked(self, chip):
        if self._active_chip is chip:
            return
        self._active_chip = chip
        QTimer.singleShot(0, self.refresh)

    def _clear_cards(self):
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def refresh(self):
        self.setUpdatesEnabled(False)
        self.cards_widget.setUpdatesEnabled(False)
        self.scroll.setUpdatesEnabled(False)

        try:
            self._clear_cards()

            # 1. Fetch data based on filter
            if self._active_chip is self.chip_archived:
                from repositories import activities_repo
                acts = activities_repo.list_archived()
            elif self._active_chip is self.chip_active:
                acts = activity_service.list_active()
            else:
                acts = activity_service.list_all()

            # 2. Apply search
            query = self.search.text().strip().lower()
            if query:
                acts = [a for a in acts if query in a.name.lower()]

            # 3. Build cards
            has_cards = False
            insert_pos = self.cards_layout.count() - 1

            for a in acts:
                has_cards = True
                card = ActivityCard(a, self._open_detail, parent=self.cards_widget)
                self.cards_layout.insertWidget(insert_pos, card)
                insert_pos += 1

            # 4. Toggle empty states
            if has_cards:
                self.scroll.show()
                self.empty_first_run.hide()
                self.empty_no_results.hide()
            else:
                self.scroll.hide()
                filtered = bool(query) or self._active_chip is not self.chip_all
                self.empty_no_results.setVisible(filtered)
                self.empty_first_run.setVisible(not filtered)

        finally:
            self.setUpdatesEnabled(True)
            self.cards_widget.setUpdatesEnabled(True)
            self.scroll.setUpdatesEnabled(True)
            self.cards_widget.update()
            self.scroll.update()

    def _on_add(self):
        dlg = ActivityFormDialog(parent=self)
        if dlg.exec():
            QTimer.singleShot(0, self.refresh)

    def _open_detail(self, activity_id):
        detail = ActivityDetailScreen(activity_id, on_back=self._close_detail, parent=self)
        self.stack.addWidget(detail)
        self.stack.setCurrentWidget(detail)

    def _close_detail(self):
        curr = self.stack.currentWidget()
        if not curr:
            return
        self.stack.setCurrentIndex(0)
        self.stack.removeWidget(curr)
        curr.setParent(None)
        curr.hide()
        curr.deleteLater()
        QTimer.singleShot(0, self.refresh)