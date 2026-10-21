"""
Championships Main Screen — Compact Card Layout with Grouping & Filters.

Flash fixes in this version (see notes in the chat):
  * Every widget is created WITH its final parent, so nothing is ever a
    parentless top-level widget that a layout later re-parents.
  * restyle() no longer calls refresh(). It used to rebuild every card on
    construction, on theme change, and (via _on_chip_clicked) twice per
    chip click.
  * Cards are cleared with hide() -> setParent(None) -> deleteLater().
    The explicit hide() marks the widget as hidden-on-purpose, so a
    show that Qt queued when the card was added can no longer pop the
    orphaned card up as a tiny top-level window.
  * The two empty states are created once and toggled, instead of being
    destroyed and re-created on every refresh.
  * Chips use make_segment() + a QButtonGroup (theme.py v4.2 styles the
    :checked state), instead of per-chip inline stylesheets.
"""
from datetime import date
import os
import sys
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QFrame, QLineEdit, QStackedWidget, QMenu, QInputDialog,
    QButtonGroup,
)
from qtpy.QtCore import Qt,QTimer
from qtpy.QtGui import QAction


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import championships_repo
from services import activity_service, championship_service
from ui.dialogs.championship_form_dialog import ChampionshipFormDialog
from ui.screens.championship_detail_screen import ChampionshipDetailScreen
from ui.theme import theme, ThemedWidget, make_danger, make_secondary, make_segment
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.utils import Debouncer
from ui.components import Toolbar, EmptyState
from ui.message_box import ask, warn
from logic.arabic_normalize import normalize_arabic


class ChampionshipCard(ThemedWidget, QFrame):
    """Compact row card for the championships list."""

    def __init__(self, champ, metrics, on_click, on_menu, parent=None):
        QFrame.__init__(self, parent)
        self.setObjectName("champCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.champ = champ
        self.metrics = metrics
        self._on_click = on_click
        self._on_menu = on_menu
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Left: Status Icon & Date
        col1 = QVBoxLayout()
        col1.setSpacing(4)
        status = championship_service.get_status(self.champ.event_date)

        # Labels are parented to the card from the start (parent=self).
        self.date_label = QLabel(self.champ.event_date, self)
        self.status_label = QLabel(t(f"champ.status.{status}"), self)
        col1.addWidget(self.date_label)
        col1.addWidget(self.status_label)
        layout.addLayout(col1)

        # Middle: Title & Activity
        col2 = QVBoxLayout()
        col2.setSpacing(4)
        self.title = QLabel(self.champ.name, self)
        act = activity_service.get(self.champ.activity_id) if self.champ.activity_id else None
        act_name = activity_service.get_localized_name(act) if act else "—"
        self.sub = QLabel(act_name, self)
        col2.addWidget(self.title)
        col2.addWidget(self.sub)
        layout.addLayout(col2, stretch=1)

        # Right: Metrics (Participants & Medals)
        col3 = QVBoxLayout()
        col3.setSpacing(4)
        col3.setAlignment(Qt.AlignmentFlag.AlignRight)

        p_count = self.metrics.get("participants", 0)
        self.part_label = QLabel(t("champ.card.participants", n=p_count), self)

        # Medal string (e.g. 🥇 2  🥈 1)
        medals = []
        if self.metrics.get("gold", 0) > 0: medals.append(f"🥇 {self.metrics['gold']}")
        if self.metrics.get("silver", 0) > 0: medals.append(f"🥈 {self.metrics['silver']}")
        if self.metrics.get("bronze", 0) > 0: medals.append(f"🥉 {self.metrics['bronze']}")
        self.medal_label = QLabel("  ".join(medals) if medals else "—", self)

        col3.addWidget(self.part_label)
        col3.addWidget(self.medal_label)
        layout.addLayout(col3)

    def restyle(self):
        tm = theme()
        self.setStyleSheet(
            f"QFrame#champCard {{"
            f"  background: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['md']}px;"
            f"}}"
            f"QFrame#champCard:hover {{"
            f"  border: 1px solid {tm.color('primary')};"
            f"}}"
        )
        self.title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {tm.color('text')};")
        self.sub.setStyleSheet(f"font-size: 12px; color: {tm.color('text_secondary')};")
        self.date_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {tm.color('text')};")

        status = championship_service.get_status(self.champ.event_date)
        color = tm.color("primary") if status == "upcoming" else (tm.color("success") if status == "today" else tm.color("text_secondary"))
        self.status_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {color};")

        self.part_label.setStyleSheet(f"font-size: 12px; color: {tm.color('text_secondary')};")
        self.medal_label.setStyleSheet(f"font-size: 14px; font-weight: bold;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self.champ.championship_id)
        elif event.button() == Qt.MouseButton.RightButton:
            self._on_menu(event.globalPos(), self.champ)
        super().mousePressEvent(event)


class ChampionshipsScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._dirty = True
        self._build_ui()
        self._init_theme()

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self._dirty = False
            self.refresh()

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
        self.search.setPlaceholderText(t("champ.search"))
        self.search.setProperty("cssClass", "search")
        self.search.setMinimumWidth(200)
        self.debouncer = Debouncer(250, self.refresh, parent=self)
        self.search.textChanged.connect(self.debouncer.trigger)

        self.add_btn = QPushButton("+ " + t("champ.add"))
        self.add_btn.clicked.connect(self._on_add)

        self.toolbar.add_leading(self.search, stretch=1)
        self.toolbar.add_trailing(self.add_btn)
        layout.addWidget(self.toolbar) # <-- No stretch

        # Segment chips (filters) — styled by theme.py's "segment" class
        chips_container = QWidget(page)
        chips_row = QHBoxLayout(chips_container)
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(SPACING["sm"])
        
        self.chip_all = QPushButton(t("champ.filter.all"), chips_container)
        self.chip_upcoming = QPushButton(t("champ.filter.upcoming"), chips_container)
        self.chip_finished = QPushButton(t("champ.filter.finished"), chips_container)

        self.chips_group = [self.chip_all, self.chip_upcoming, self.chip_finished]
        self._chip_buttons = QButtonGroup(self)
        self._chip_buttons.setExclusive(True)
        self._active_chip = self.chip_all

        for chip in self.chips_group:
            chip.setCheckable(True)
            make_segment(chip)
            self._chip_buttons.addButton(chip)
            chip.clicked.connect(lambda checked, c=chip: self._on_chip_clicked(c))
            chips_row.addWidget(chip)
        self.chip_all.setChecked(True)
        chips_row.addStretch()
        
        layout.addWidget(chips_container) # <-- No stretch

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
        layout.addWidget(self.scroll, stretch=1) # <-- STRETCH=1

        # Two empty states, created once and toggled in refresh().
        self.empty_first_run = EmptyState(icon="🏆", message=t("champ.empty"))
        self.empty_no_results = EmptyState(icon="🏆", message=t("champ.empty.no_results"))
        for empty in (self.empty_first_run, self.empty_no_results):
            empty.hide()
            layout.addWidget(empty, stretch=1) # <-- STRETCH=1

        self.stack.addWidget(page)
        self.stack.setCurrentIndex(0)

    def restyle(self):
        tm = theme()
        # Force the dialog background and text to match the theme
        self.setStyleSheet(
            f"QDialog {{ background-color: {tm.color('surface')}; }}"
            f"QLabel {{ color: {tm.color('text')}; font-size: 14px; }}"
            f"QComboBox {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"  color: {tm.color('text')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 4px 8px;"
            f"}}"
        )

    def _on_chip_clicked(self, chip):
        if self._active_chip is chip:
            return
        self._active_chip = chip
        self.refresh()

    def _clear_cards(self):
        """Remove every card / section header, keeping the trailing stretch."""
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                # hide() FIRST: marks the widget as explicitly hidden so a show
                # queued by the layout can't resurrect it as a top-level window.
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def refresh(self):
        # Freeze painting while we rebuild so the list doesn't flicker
        # and the layout doesn't thrash during empty-state toggling.
        self.setUpdatesEnabled(False)
        self.cards_widget.setUpdatesEnabled(False)
        self.scroll.setUpdatesEnabled(False)

        try:
            self._clear_cards()

            champs = championships_repo.list_championships()
            metrics = championship_service.get_metrics_for_all_championships()

            # Search filter
            query = self.search.text().strip()
            if query:
                norm_q = normalize_arabic(query).lower()
                champs = [c for c in champs if norm_q in normalize_arabic(c.name or "").lower()]

            # Split into upcoming / finished
            upcoming = []
            finished = []
            for c in champs:
                status = championship_service.get_status(c.event_date)
                if status in ("upcoming", "today"):
                    upcoming.append(c)
                else:
                    finished.append(c)

            # Sort: Upcoming (soonest first), Finished (newest first)
            upcoming.sort(key=lambda x: x.event_date)
            finished.sort(key=lambda x: x.event_date, reverse=True)

            show_upcoming = self._active_chip in (self.chip_all, self.chip_upcoming)
            show_finished = self._active_chip in (self.chip_all, self.chip_finished)

            has_cards = False
            insert_pos = self.cards_layout.count() - 1

            if show_upcoming and upcoming:
                has_cards = True
                self._add_section_header(t("champ.filter.upcoming"), insert_pos)
                insert_pos += 1
                for c in upcoming:
                    self._add_card(c, metrics, insert_pos)
                    insert_pos += 1

            if show_finished and finished:
                has_cards = True
                self._add_section_header(t("champ.filter.finished"), insert_pos)
                insert_pos += 1
                for c in finished:
                    self._add_card(c, metrics, insert_pos)
                    insert_pos += 1

            # Toggle the persistent empty states
            if has_cards:
                self.scroll.show()
                self.empty_first_run.hide()
                self.empty_no_results.hide()
            else:
                self.scroll.hide()
                filtered = bool(query) or self._active_chip is not self.chip_all
                self.empty_no_results.setVisible(filtered)
                self.empty_first_run.setVisible(not filtered)

        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Failed to refresh championships")
            
        finally:
            # Unfreeze painting in one single frame
            self.setUpdatesEnabled(True)
            self.cards_widget.setUpdatesEnabled(True)
            self.scroll.setUpdatesEnabled(True)
            self.cards_widget.update()
            self.scroll.update()

    def _add_section_header(self, text, pos):
        lbl = QLabel(text, self.cards_widget)
        # Colour comes from theme.py's "muted" label class, so it follows the
        # theme without being rebuilt; only size/weight/margin are inline.
        lbl.setProperty("cssClass", "muted")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 8px;")
        self.cards_layout.insertWidget(pos, lbl)

    def _add_card(self, champ, metrics, pos):
        card = ChampionshipCard(
            champ,
            metrics.get(champ.championship_id, {}),
            self._open_detail,
            self._show_context_menu,
            parent=self.cards_widget,
        )
        self.cards_layout.insertWidget(pos, card)

    def _show_context_menu(self, global_pos, champ):
        menu = QMenu(self)

        act_open = menu.addAction(t("champ.menu.open"))
        act_edit = menu.addAction(t("champ.menu.edit"))
        act_dup = menu.addAction(t("champ.menu.duplicate"))
        menu.addSeparator()
        act_del = menu.addAction(t("champ.menu.delete"))

        # Apply permissions (assuming app_state.can)
        from app_state import app
        can_manage = app.can("championships.manage")

        act_edit.setEnabled(can_manage)
        act_dup.setEnabled(can_manage)
        act_del.setEnabled(can_manage)

        action = menu.exec(global_pos)

        if action == act_open:
            self._open_detail(champ.championship_id)
        elif action == act_edit:
            dlg = ChampionshipFormDialog(champ, parent=self)
            if dlg.exec():
                QTimer.singleShot(0, self.refresh)
        elif action == act_dup:
            self._on_duplicate(champ)
        elif action == act_del:
            self._on_delete(champ)

    def _on_duplicate(self, champ):
        date_str, ok = QInputDialog.getText(
            self, t("champ.menu.duplicate_title"), t("champ.menu.duplicate_msg"), text=champ.event_date
        )
        if ok and date_str:
            try:
                # Create copy
                championship_service.create_championship(
                    f"{champ.name} (Copy)", date_str, champ.activity_id,
                    champ.location, champ.entry_fee, champ.notes
                )
                QTimer.singleShot(0, self.refresh)
            except Exception as e:
                warn(self, t("msg.error"), str(e))

    def _on_delete(self, champ):
        if ask(self, t("champ.confirm.delete_title"), t("champ.confirm.delete_msg", name=champ.name)):
            championships_repo.archive_championship(champ.championship_id)
            QTimer.singleShot(0, self.refresh)

    def _on_add(self):
        dlg = ChampionshipFormDialog(parent=self)
        if dlg.exec():
            # Defer the refresh by one event-loop tick so the dialog's
            # dismissal frame is fully painted before we rebuild the list.
            
            QTimer.singleShot(0, self.refresh)

    def _open_detail(self, champ_id):
        detail = ChampionshipDetailScreen(champ_id, on_back=self._close_detail, parent=self)
        self.stack.addWidget(detail)
        self.stack.setCurrentWidget(detail)

    def _close_detail(self):
        curr = self.stack.currentWidget()
        if not curr:
            return
            
        # 1. Switch the stack back to the list view
        self.stack.setCurrentIndex(0)
        
        # 2. Remove from the stack
        self.stack.removeWidget(curr)
        
        # 3. CRITICAL: Detach from the main window and hide immediately!
        # This prevents Qt from trying to draw it as a floating window.
        curr.setParent(None)
        curr.hide()
        
        # 4. Delete it safely in the next event loop cycle
        curr.deleteLater()
        
        # 5. Refresh the list
        QTimer.singleShot(0, self.refresh)
