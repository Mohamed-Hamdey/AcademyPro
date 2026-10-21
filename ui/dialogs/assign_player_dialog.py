"""
Assign Players Dialog — v5.

Fixes and changes from the previous version:

  BUGS
  * Save never worked: cellWidget(i, 2/3) returns the *container* QWidget, not
    the QComboBox / QDoubleSpinBox inside it, so `.currentData()` raised
    AttributeError (shown as an error banner). Selection, belt and weight now
    live in a per-player state dict that the row widgets write into.
  * "Default belt" / "Default weight" did nothing. They now fill players that
    have no stored belt/weight, and follow changes until you edit that row.
  * Searching rebuilt the table and silently threw away checked rows and edited
    belts/weights. State now survives searching; the Assign (N) count covers
    every selected player, visible or not.
  * Pressing Enter in the search box triggered the default Assign button,
    which also records payments. The buttons are no longer default buttons.
  * A failure half-way through registering left earlier players registered but
    still selectable, so a retry would register (and charge) them twice. Each
    success is now recorded immediately; the table reloads to show them as
    "already assigned".
  * Removed dead code: an unused header checkbox + widget, never added to any
    layout.

  UX
  * Click anywhere on a row to tick/untick it. Checked rows are highlighted.
  * One "Select all" checkbox that follows the rows (acts on visible,
    unassigned rows; unticks itself when you untick a row).
  * Players who are not yet assigned are listed first; assigned ones last.
  * Header text aligned with the data; weight suffix comes from the same
    translation key as the footer spin box (was a hard-coded " kg").
  * Same v5 look as the other dialogs: header, divider, themed error banner.
  * No new translation keys.
"""
from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QDoubleSpinBox,
    QLineEdit, QPushButton, QLabel, QTableWidgetItem, QCheckBox,
    QWidget, QTableWidget, QSizePolicy,
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


_BELTS = ("white", "yellow", "orange", "green", "blue", "brown", "black")
_DEFAULT_WEIGHT = 60.0


class AssignPlayerDialog(ThemedWidget, QDialog):
    def __init__(self, championship_id, existing_player_ids, parent=None):
        QDialog.__init__(self, parent)
        self.championship_id = championship_id
        self.existing_ids = set(existing_player_ids)
        self.champ = championships_repo.get_championship(self.championship_id)

        # player_id -> {"checked", "belt", "weight", "belt_dirty", "weight_dirty",
        #               "belt_stored", "weight_stored", "name"}
        self._state = {}
        # player_id -> {"row", "chk", "belt", "weight"} for the rows on screen
        self._row_widgets = {}
        self._visible_ids = []
        self._registered_any = False

        self.setWindowTitle(t("champ.assign.title"))
        self.setMinimumSize(760, 560)
        self._build_ui()
        self._init_theme()
        self._reload_players()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        root.setSpacing(SPACING["md"])

        # ---- Header: badge + title + "championship · activity" ----
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

        # ---- Search ----
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText(t("champ.assign.search"))
        self.search_input.setProperty("cssClass", "search")
        self.debouncer = Debouncer(250, self._reload_players, parent=self)
        self.search_input.textChanged.connect(self.debouncer.trigger)
        self.search_input.returnPressed.connect(self._on_search_enter)
        root.addWidget(self.search_input)

        # ---- Select all (acts on the visible, unassigned rows) ----
        select_row = QHBoxLayout()
        select_row.setContentsMargins(0, 0, 0, 0)
        self.select_all_check = QCheckBox(t("champ.assign.select_all"), self)
        self.select_all_check.toggled.connect(self._on_select_all)
        select_row.addWidget(self.select_all_check)
        select_row.addStretch()
        root.addLayout(select_row)

        # ---- Table ----
        self.table = make_standard_table(
            headers=["", t("champ.col.player"), t("champ.col.belt"), t("champ.col.weight")],
            column_modes=["fixed", "stretch", "fixed", "fixed"],
            parent=self,
        )
        self.table.setColumnWidth(0, 56)    # checkbox
        self.table.setColumnWidth(2, 170)   # belt
        self.table.setColumnWidth(3, 150)   # weight
        self.table.verticalHeader().setDefaultSectionSize(54)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)

        # Header text aligned like the data: player name at the start edge,
        # the widget columns centred.
        for col, align in (
            (1, Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter),
            (2, Qt.AlignmentFlag.AlignCenter),
            (3, Qt.AlignmentFlag.AlignCenter),
        ):
            item = self.table.horizontalHeaderItem(col)
            if item is not None:
                item.setTextAlignment(align)

        root.addWidget(self.table, 1)

        # ---- Footer: defaults + actions ----
        bottom = QHBoxLayout()
        bottom.setSpacing(SPACING["md"])

        bottom.addWidget(QLabel(t("champ.assign.default_belt"), self))
        self.default_belt = QComboBox(self)
        for belt_key in _BELTS:
            self.default_belt.addItem(t(f"belt.{belt_key}"), belt_key)
        self.default_belt.currentIndexChanged.connect(self._on_default_belt_changed)
        bottom.addWidget(self.default_belt)

        bottom.addWidget(QLabel(t("champ.assign.default_weight"), self))
        self.default_weight = QDoubleSpinBox(self)
        self.default_weight.setMinimum(10)
        self.default_weight.setMaximum(300)
        self.default_weight.setDecimals(1)
        self.default_weight.setValue(_DEFAULT_WEIGHT)
        self.default_weight.setSuffix(t("champ.assign.weight_suffix"))
        self.default_weight.setMinimumWidth(120)
        self.default_weight.valueChanged.connect(self._on_default_weight_changed)
        bottom.addWidget(self.default_weight)

        bottom.addStretch()

        cancel_btn = QPushButton(t("msg.cancel"), self)
        make_secondary(cancel_btn)
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)

        # Not a default button on purpose: Enter in the search box must never
        # register players (and record payments).
        self.save_btn = QPushButton(t("champ.assign.btn", n=0), self)
        self.save_btn.setAutoDefault(False)
        self.save_btn.setDefault(False)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save)
        bottom.addWidget(self.save_btn)

        root.addLayout(bottom)

        # ---- Error banner ----
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

        # Unassigned players first, already-assigned ones last (stable sort).
        rows = sorted(rows, key=lambda r: r["player"].player_id in self.existing_ids)

        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(0)          # also releases the old cell widgets
            self.table.setRowCount(len(rows))
            self._row_widgets = {}
            self._visible_ids = []
            for i, r in enumerate(rows):
                self._build_row(i, r["player"])
        finally:
            self.table.setUpdatesEnabled(True)

        self._update_selected_count()

    def _state_for(self, p):
        st = self._state.get(p.player_id)
        if st is not None:
            return st

        stored_belt = getattr(p, "belt", None)
        stored_weight = getattr(p, "weight_kg", None)
        try:
            weight = float(stored_weight) if stored_weight else float(self.default_weight.value())
        except (TypeError, ValueError):
            stored_weight = None
            weight = float(self.default_weight.value())

        st = {
            "name": p.full_name,
            "checked": False,
            "belt": str(stored_belt).lower() if stored_belt else self.default_belt.currentData(),
            "weight": weight,
            "belt_stored": bool(stored_belt),
            "weight_stored": bool(stored_weight),
            "belt_dirty": False,
            "weight_dirty": False,
        }
        self._state[p.player_id] = st
        return st

    def _build_row(self, i, p):
        pid = p.player_id
        assigned = pid in self.existing_ids
        st = self._state_for(p)
        viewport = self.table.viewport()

        # Items under the cell widgets, so rows can be highlighted evenly.
        for col in (0, 2, 3):
            self.table.setItem(i, col, QTableWidgetItem())

        # ---- 0. checkbox ----
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

        # ---- 1. name ----
        name = p.full_name
        if assigned:
            name += f"  ({t('champ.assign.already')})"
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.ItemDataRole.UserRole, pid)
        name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter)
        if assigned:
            name_item.setForeground(QColor(theme().color("text_secondary")))
        self.table.setItem(i, 1, name_item)

        # ---- 2. belt ----
        belt_cell = QWidget(viewport)
        belt_lay = QHBoxLayout(belt_cell)
        belt_lay.setContentsMargins(8, 3, 8, 3)
        belt_lay.setSpacing(0)
        belt_combo = QComboBox(belt_cell)
        belt_combo.setFixedHeight(32)
        belt_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for belt_key in _BELTS:
            belt_combo.addItem(t(f"belt.{belt_key}"), belt_key)
        idx = belt_combo.findData(st["belt"])
        belt_combo.setCurrentIndex(idx if idx >= 0 else 0)
        belt_combo.setEnabled(not assigned)
        belt_combo.currentIndexChanged.connect(
            lambda _i, pid=pid, combo=belt_combo: self._on_belt_edited(pid, combo)
        )
        belt_lay.addWidget(belt_combo)
        self.table.setCellWidget(i, 2, belt_cell)

        # ---- 3. weight ----
        weight_cell = QWidget(viewport)
        weight_lay = QHBoxLayout(weight_cell)
        weight_lay.setContentsMargins(8, 3, 8, 3)
        weight_lay.setSpacing(0)
        weight_spin = QDoubleSpinBox(weight_cell)
        weight_spin.setMinimum(10)
        weight_spin.setMaximum(300)
        weight_spin.setDecimals(1)
        weight_spin.setSingleStep(0.5)
        weight_spin.setFixedHeight(32)
        weight_spin.setMinimumWidth(110)
        weight_spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        weight_spin.setSuffix(t("champ.assign.weight_suffix"))
        weight_spin.setValue(st["weight"])
        weight_spin.setEnabled(not assigned)
        weight_spin.valueChanged.connect(
            lambda value, pid=pid: self._on_weight_edited(pid, value)
        )
        weight_lay.addWidget(weight_spin)
        self.table.setCellWidget(i, 3, weight_cell)

        self._row_widgets[pid] = {
            "row": i, "chk": chk, "belt": belt_combo, "weight": weight_spin,
        }
        self._visible_ids.append(pid)
        self._paint_row(i, pid)

    def _paint_row(self, row, pid):
        """Highlight ticked rows. Assigned rows are never highlighted."""
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
        """Clicking anywhere on a row (outside its own controls) toggles it."""
        if row < 0 or row >= len(self._visible_ids):
            return
        pid = self._visible_ids[row]
        if pid in self.existing_ids:
            return
        w = self._row_widgets.get(pid)
        if w is not None:
            w["chk"].toggle()       # emits toggled -> _on_row_toggled

    def _on_row_toggled(self, pid, checked):
        st = self._state.get(pid)
        if st is not None:
            st["checked"] = bool(checked)
        w = self._row_widgets.get(pid)
        if w is not None:
            self._paint_row(w["row"], pid)
        self._update_selected_count()

    def _on_belt_edited(self, pid, combo):
        st = self._state.get(pid)
        if st is not None:
            st["belt"] = combo.currentData()
            st["belt_dirty"] = True

    def _on_weight_edited(self, pid, value):
        st = self._state.get(pid)
        if st is not None:
            st["weight"] = float(value)
            st["weight_dirty"] = True

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

    def _on_default_belt_changed(self, _index=0):
        belt = self.default_belt.currentData()
        for pid, st in self._state.items():
            if pid in self.existing_ids or st["belt_stored"] or st["belt_dirty"]:
                continue
            st["belt"] = belt
            w = self._row_widgets.get(pid)
            if w is not None:
                idx = w["belt"].findData(belt)
                if idx >= 0:
                    w["belt"].blockSignals(True)
                    w["belt"].setCurrentIndex(idx)
                    w["belt"].blockSignals(False)

    def _on_default_weight_changed(self, value):
        for pid, st in self._state.items():
            if pid in self.existing_ids or st["weight_stored"] or st["weight_dirty"]:
                continue
            st["weight"] = float(value)
            w = self._row_widgets.get(pid)
            if w is not None:
                w["weight"].blockSignals(True)
                w["weight"].setValue(float(value))
                w["weight"].blockSignals(False)

    def _selected_players(self):
        """[(player_id, state)] for every ticked player, visible or not."""
        return [
            (pid, st) for pid, st in self._state.items()
            if st["checked"] and pid not in self.existing_ids
        ]

    def _update_selected_count(self):
        count = len(self._selected_players())
        self.save_btn.setText(t("champ.assign.btn", n=count))
        self.save_btn.setEnabled(count > 0)

        # Keep "Select all" in step with the visible, unassigned rows.
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

        for pid, st in pending:
            try:
                championship_service.register_player(
                    self.championship_id,
                    pid,
                    st["weight"],
                    st["belt"],
                    "",
                    record_payment=True,
                )
            except Exception as e:
                # Players registered so far stay registered. Reload so they show
                # as "already assigned" and cannot be submitted (and charged) twice.
                self._show_error(f"{st['name']}: {e}")
                self._reload_players()
                return

            self.existing_ids.add(pid)
            st["checked"] = False
            self._registered_any = True

        self.accept()

    def reject(self):
        # If some players were already registered before an error, closing the
        # dialog must still report "accepted" so the caller refreshes its list.
        if self._registered_any:
            self.accept()
        else:
            super().reject()