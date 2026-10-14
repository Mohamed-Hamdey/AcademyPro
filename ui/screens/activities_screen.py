"""
Activities management screen — v4 design.

Manager-only. List of all activities, with:
  * Toolbar (search + Add)
  * Table: name (English · Arabic), days, subscriptions count, status
  * Actions: Deactivate / Reactivate
  * "Show inactive" toggle to reveal soft-deleted activities
  * Double-click a row → edit
"""

import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QLabel,
)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import activity_service
from repositories.activities_repo import Activity
from ui.components import Toolbar, SectionCard, EmptyState
from ui.dialogs.activity_form_dialog import ActivityFormDialog
from ui.theme import theme, ThemedWidget, make_secondary, make_danger
from ui.design import SPACING
from ui.i18n import t
from ui.message_box import warn, ask


class ActivitiesScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._rows = []
        self._build_ui()
        self.refresh()
        self._init_theme()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        self.toolbar = Toolbar()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("activities.search_placeholder"))
        self.search_input.setProperty("cssClass", "search")
        self.search_input.setMinimumWidth(240)
        self.search_input.textChanged.connect(self.refresh)

        self.show_inactive_checkbox = QCheckBox(t("activities.show_inactive"))
        self.show_inactive_checkbox.stateChanged.connect(self.refresh)

        self.add_button = QPushButton(t("activities.add"))
        self.add_button.clicked.connect(self._on_add)

        self.toolbar.add_leading(self.search_input, stretch=1)
        self.toolbar.add_leading(self.show_inactive_checkbox)
        self.toolbar.add_trailing(self.add_button)

        root.addWidget(self.toolbar)

        self.table_card = SectionCard(title=t("activities.title"))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            t("activities.col.name"),
            t("activities.col.days"),
            t("activities.col.subscriptions"),
            t("activities.col.status"),
            t("activities.col.color"),
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 60)

        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.horizontalHeader().setFixedHeight(36)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.cellDoubleClicked.connect(lambda *_: self._on_edit())

        self.table_card.body.addWidget(self.table)

        # Two empty states — one for "no activities at all" (first run,
        # with an Add CTA), one for "no matches" (no CTA).
        self.empty_first_run = EmptyState(
            icon="🏃",
            message=t("activities.empty"),
            action_text=t("activities.add"),
            on_action=self._on_add,
        )
        self.empty_first_run.hide()
        self.table_card.body.addWidget(self.empty_first_run)

        self.empty_no_results = EmptyState(
            icon="🔍",
            message=t("activities.no_results"),
        )
        self.empty_no_results.hide()
        self.table_card.body.addWidget(self.empty_no_results)

        # --- Action row (inside the card, right-aligned) ---
        self.table_card.body.addSpacing(SPACING["sm"])

        action_row = QHBoxLayout()
        action_row.setSpacing(SPACING["sm"])

        self.toggle_button = QPushButton(t("activities.action.deactivate"))
        make_danger(self.toggle_button)
        self.toggle_button.clicked.connect(self._on_toggle_active)
        self.toggle_button.setEnabled(False)

        action_row.addStretch()
        action_row.addWidget(self.toggle_button)

        self.table_card.body.addLayout(action_row)

        # Card hugs its content; leftover space collapses below.
        root.addWidget(self.table_card)
        root.addStretch()

    # ---------- theming ----------

    def restyle(self):
        if hasattr(self, "_rows"):
            self._render_rows(self._rows)

    # ---------- data ----------

    def refresh(self):
        show_inactive = self.show_inactive_checkbox.isChecked()
        all_acts = activity_service.list_all() if show_inactive else activity_service.list_active()

        query = self.search_input.text().strip().lower()
        if query:
            all_acts = [
                a for a in all_acts
                if query in a.name_en.lower() or query in a.name_ar.lower()
            ]

        self._rows = all_acts
        self._render_rows(all_acts)

    def _render_rows(self, activities):
        search_text = self.search_input.text().strip()

        # ---- Empty-state dispatch ----
        if not activities:
            self.table.hide()
            if search_text:
                self.empty_first_run.hide()
                self.empty_no_results.show()
            else:
                self.empty_no_results.hide()
                self.empty_first_run.show()
            self._update_actions()
            return

        self.table.show()
        self.empty_first_run.hide()
        self.empty_no_results.hide()

        self.table.setRowCount(len(activities))
        tm = theme()

        # Hide the color column entirely if no visible activity has a color.
        has_any_color = any(a.color for a in activities)
        self.table.setColumnHidden(4, not has_any_color)

        for i, a in enumerate(activities):
            # Name — "Kung Fu · الكونغ فو"
            name = f"{a.name_en} · {a.name_ar}"
            name_item = QTableWidgetItem(name)
            if not a.active:
                name_item.setForeground(QColor(tm.color("text_secondary")))
            self.table.setItem(i, 0, name_item)

            # Days — also dimmed for inactive
            days_str = ", ".join(t(f"weekday.{d.lower()}") for d in a.default_days)
            days_item = QTableWidgetItem(days_str)
            if not a.active:
                days_item.setForeground(QColor(tm.color("text_secondary")))
            self.table.setItem(i, 1, days_item)

            # Subscriptions — "active / total"
            active_count = activity_service.count_active_references(a.activity_id)
            total_count = activity_service.count_references(a.activity_id)
            count_item = QTableWidgetItem(f"{active_count} / {total_count}")
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if not a.active:
                count_item.setForeground(QColor(tm.color("text_secondary")))
            self.table.setItem(i, 2, count_item)

            # Status
            status_text = (
                t("activities.status.active") if a.active
                else t("activities.status.inactive")
            )
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            color = tm.color("success") if a.active else tm.color("text_secondary")
            bg = tm.color("success_soft") if a.active else tm.color("neutral_soft")
            status_item.setForeground(QColor(color))
            status_item.setBackground(QColor(bg))
            self.table.setItem(i, 3, status_item)

            # Color swatch — only rendered when the column is visible
            if has_any_color:
                color_item = QTableWidgetItem()
                if a.color:
                    color_item.setBackground(QColor(a.color))
                color_item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                )
                self.table.setItem(i, 4, color_item)

        self._update_actions()
    def _selected(self) -> Activity:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._rows):
            return None
        return self._rows[idx]

    def _update_actions(self):
        a = self._selected()
        enabled = a is not None
        self.toggle_button.setEnabled(enabled)

        # Always reset text/style first, so a stale "Reactivate" label
        # doesn't linger after the selection is cleared.
        if a is None or a.active:
            self.toggle_button.setText(t("activities.action.deactivate"))
            make_danger(self.toggle_button)
        else:
            self.toggle_button.setText(t("activities.action.reactivate"))
            make_secondary(self.toggle_button)

    # ---------- actions ----------

    def _on_add(self):
        dlg = ActivityFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _on_edit(self):
        a = self._selected()
        if a is None:
            return
        dlg = ActivityFormDialog(activity=a, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_toggle_active(self):
        a = self._selected()
        if a is None:
            return

        if a.active:
            # Deactivating — warn about references
            refs = activity_service.count_references(a.activity_id)
            msg_key = "activities.confirm.deactivate_with_refs" if refs > 0 else "activities.confirm.deactivate"
            if not ask(
                self,
                t("activities.confirm.title"),
                t(msg_key, name=a.name_en, count=refs),
            ):
                return
            activity_service.deactivate(a.activity_id)
        else:
            activity_service.reactivate(a.activity_id)

        self.refresh()