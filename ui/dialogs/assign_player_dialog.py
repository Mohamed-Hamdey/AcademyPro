"""
Assign Players Dialog — v6 (Read-only Belt/Weight).

Belt and weight are pulled directly from the player's profile. The dialog
simply lists eligible players with their current stats and lets you check
the ones you want to assign.
"""

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidgetItem, QCheckBox, QWidget, QTableWidget, QSizePolicy,
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QBrush

from repositories import players_repo, championships_repo
from services import championship_service, activity_service
from ui.table_helpers import make_standard_table
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.utils import Debouncer
from ui.form_helpers import hex_, make_divider, style_divider


class AssignPlayerDialog(ThemedWidget, QDialog):
    def __init__(self, championship_id, existing_player_ids, parent=None):
        QDialog.__init__(self, parent)
        
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)
        
        try:
            self.championship_id = championship_id
            self.existing_ids = set(existing_player_ids)
            self.champ = championships_repo.get_championship(self.championship_id)

            self._state = {}  # player_id -> {"checked": bool, "name": str}
            self._row_widgets = {}  # player_id -> {"row": int, "chk": QCheckBox}
            self._visible_ids = []

            self.setWindowTitle(t("champ.assign.title"))
            self.setMinimumSize(760, 560)
            self._build_ui()
            self._init_theme()
            self._reload_players()
        finally:
            self.setUpdatesEnabled(True)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
            self.update()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        root.setSpacing(SPACING["md"])

        # Header
        header = QHBoxLayout()
        header.setSpacing(SPACING["lg"])
        header.setContentsMargins(0, 0, 0, 0)

        self.badge = QLabel("🏆", self)
        self.badge.setFixedSize(48, 48)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.header_title = QLabel(t("champ.assign.title"), self)
        self.header_sub = QLabel(self._header_subtitle(), self)
        text_col.addStretch(1)
        text_col.addWidget(self.header_title)
        text_col.addWidget(self.header_sub)
        text_col.addStretch(1)

        header.addWidget(self.badge)
        header.addLayout(text_col, 1)
        root.addLayout(header)

        self.divider = make_divider(self, "assignDivider")
        root.addWidget(self.divider)

        # Search
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText(t("champ.assign.search"))
        self.search_input.setProperty("cssClass", "search")
        self.debouncer = Debouncer(250, self._reload_players, parent=self)
        self.search_input.textChanged.connect(self.debouncer.trigger)
        self.search_input.returnPressed.connect(self._on_search_enter)
        root.addWidget(self.search_input)

        # Select all
        select_row = QHBoxLayout()
        select_row.setContentsMargins(0, 0, 0, 0)
        self.select_all_check = QCheckBox(t("champ.assign.select_all"), self)
        self.select_all_check.toggled.connect(self._on_select_all)
        select_row.addWidget(self.select_all_check)
        select_row.addStretch()
        root.addLayout(select_row)

        # Table
        self.table = make_standard_table(
            headers=["", t("champ.col.player"), t("champ.col.belt"), t("champ.col.weight")],
            column_modes=["fixed", "stretch", "fixed", "fixed"],
            parent=self,
        )
        self.table.setColumnWidth(0, 56)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 150)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)

        for col, align in (
            (1, Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter),
            (2, Qt.AlignmentFlag.AlignCenter),
            (3, Qt.AlignmentFlag.AlignCenter),
        ):
            item = self.table.horizontalHeaderItem(col)
            if item is not None:
                item.setTextAlignment(align)

        root.addWidget(self.table, 1)

        # Footer
        bottom = QHBoxLayout()
        bottom.setSpacing(SPACING["md"])
        bottom.addStretch()

        cancel_btn = QPushButton(t("msg.cancel"), self)
        make_secondary(cancel_btn)
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)

        self.save_btn = QPushButton(t("champ.assign.btn", n=0), self)
        self.save_btn.setAutoDefault(False)
        self.save_btn.setDefault(False)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save)
        bottom.addWidget(self.save_btn)

        root.addLayout(bottom)

        # Error banner
        self.error_label = QLabel("", self)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

    def _header_subtitle(self) -> str:
        parts = []
        try:
            if self.champ is not None:
                parts.append(self.champ.name)
                if self.champ.activity_id is not None:
                    act = activity_service.get(self.champ.activity_id)
                    if act is not None:
                        parts.append(activity_service.get_localized_name(act))
        except Exception:
            pass
        return "  ·  ".join(p for p in parts if p)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def restyle(self):
        tm = theme()
        self.error_label.setStyleSheet(
            f"QLabel {{ color: {tm.color('danger')};"
            f" background-color: {tm.color('danger_soft')};"
            f" border-radius: {RADIUS['sm']}px; padding: 8px 12px; }}"
        )
        self.badge.setStyleSheet(
            f"QLabel {{ background-color: {hex_('primary_soft', 'primary', '#DBEAFE')};"
            f" border-radius: 24px; font-size: 22px; }}"
        )
        self.header_title.setStyleSheet(
            f"QLabel {{ color: {tm.color('text')}; font-size: 16px; font-weight: 700;"
            f" background: transparent; }}"
        )
        self.header_sub.setStyleSheet(
            f"QLabel {{ color: {tm.color('text_secondary')}; font-size: 12px;"
            f" background: transparent; }}"
        )
        style_divider(self.divider)
        for pid, w in self._row_widgets.items():
            self._paint_row(w["row"], pid)

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def _on_search_enter(self):
        try:
            self.debouncer.stop()
        except (AttributeError, RuntimeError):
            pass
        self._reload_players()

    def _reload_players(self):
        query = self.search_input.text().strip()

        if self.champ and self.champ.activity_id is not None:
            rows = players_repo.search_with_details_for_activity(self.champ.activity_id, query)
        else:
            rows = players_repo.search_with_details(query)

        # Unassigned first, already-assigned last
        rows = sorted(rows, key=lambda r: r["player"].player_id in self.existing_ids)

        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(0)
            self.table.setRowCount(len(rows))
            self._row_widgets = {}
            self._visible_ids = []
            for i, r in enumerate(rows):
                self._build_row(i, r["player"])
        finally:
            self.table.setUpdatesEnabled(True)

        self._update_selected_count()

    def _build_row(self, i, p):
        pid = p.player_id
        assigned = pid in self.existing_ids
        st = self._state.get(pid)
        if st is None:
            st = {"checked": False, "name": p.full_name}
            self._state[pid] = st

        viewport = self.table.viewport()

        # 0. Checkbox
        chk_cell = QWidget(viewport)
        chk_lay = QHBoxLayout(chk_cell)
        chk_lay.setContentsMargins(0, 0, 0, 0)
        chk_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk = QCheckBox(chk_cell)
        chk.setChecked(True if assigned else st["checked"])
        chk.setEnabled(not assigned)
        chk.toggled.connect(lambda checked, pid=pid: self._on_row_toggled(pid, checked))
        chk_lay.addWidget(chk)
        self.table.setCellWidget(i, 0, chk_cell)

        # 1. Name
        name = p.full_name
        if assigned:
            name += f"  ({t('champ.assign.already')})"
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.ItemDataRole.UserRole, pid)
        name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter)
        if assigned:
            name_item.setForeground(QColor(theme().color("text_secondary")))
        self.table.setItem(i, 1, name_item)

        # 2. Belt (Read-only)
        belt = p.belt or "—"
        if belt != "—":
            belt = t(f"belt.{belt.lower()}")
        belt_item = QTableWidgetItem(belt)
        belt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if assigned:
            belt_item.setForeground(QColor(theme().color("text_secondary")))
        self.table.setItem(i, 2, belt_item)

        # 3. Weight (Read-only)
        weight = f"{p.weight_kg} kg" if p.weight_kg else "—"
        weight_item = QTableWidgetItem(weight)
        weight_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if assigned:
            weight_item.setForeground(QColor(theme().color("text_secondary")))
        self.table.setItem(i, 3, weight_item)

        self._row_widgets[pid] = {"row": i, "chk": chk}
        self._visible_ids.append(pid)
        self._paint_row(i, pid)

    def _paint_row(self, row, pid):
        st = self._state.get(pid) or {}
        checked = bool(st.get("checked")) and pid not in self.existing_ids
        brush = QBrush(QColor(theme().color("primary_soft"))) if checked else QBrush()
        for col in range(4):
            item = self.table.item(row, col)
            if item is not None:
                item.setBackground(brush)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _on_cell_clicked(self, row, _col):
        if row < 0 or row >= len(self._visible_ids):
            return
        pid = self._visible_ids[row]
        if pid in self.existing_ids:
            return
        w = self._row_widgets.get(pid)
        if w is not None:
            w["chk"].toggle()

    def _on_row_toggled(self, pid, checked):
        st = self._state.get(pid)
        if st is not None:
            st["checked"] = bool(checked)
        w = self._row_widgets.get(pid)
        if w is not None:
            self._paint_row(w["row"], pid)
        self._update_selected_count()

    def _on_select_all(self, checked):
        for pid in self._visible_ids:
            if pid in self.existing_ids:
                continue
            st = self._state.get(pid)
            w = self._row_widgets.get(pid)
            if st is None or w is None:
                continue
            st["checked"] = bool(checked)
            w["chk"].blockSignals(True)
            w["chk"].setChecked(bool(checked))
            w["chk"].blockSignals(False)
            self._paint_row(w["row"], pid)
        self._update_selected_count()

    def _selected_players(self):
        return [
            pid for pid, st in self._state.items()
            if st["checked"] and pid not in self.existing_ids
        ]

    def _update_selected_count(self):
        count = len(self._selected_players())
        self.save_btn.setText(t("champ.assign.btn", n=count))
        self.save_btn.setEnabled(count > 0)

        eligible = [pid for pid in self._visible_ids if pid not in self.existing_ids]
        all_checked = bool(eligible) and all(self._state[pid]["checked"] for pid in eligible)
        self.select_all_check.blockSignals(True)
        self.select_all_check.setEnabled(bool(eligible))
        self.select_all_check.setChecked(all_checked)
        self.select_all_check.blockSignals(False)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()

    def _on_save(self):
        self.error_label.hide()
        pending = self._selected_players()
        
        if not pending:
            self._show_error(t("champ.assign.error.none_selected"))
            return

        try:
            # The service pulls belt/weight from the player's profile.
            championship_service.assign_players(self.championship_id, pending)
            self.accept()
        except Exception as e:
            self._show_error(str(e))
            self._reload_players() # Reload on error to reflect partial success if it happened