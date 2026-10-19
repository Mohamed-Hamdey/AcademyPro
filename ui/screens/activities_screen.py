"""
Activities management screen — v4 design.
"""

import os
import sys
from ui.utils import Debouncer
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QLabel,
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from services import activity_service
from repositories.activities_repo import Activity
from ui.components import Toolbar, SectionCard, EmptyState
from ui.dialogs.activity_form_dialog import ActivityFormDialog
from ui.theme import theme, ThemedWidget, make_secondary, make_danger, make_warning
from ui.design import SPACING
from ui.i18n import t
from ui.message_box import warn, ask
from ui.table_helpers import make_standard_table


class ActivitiesScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._rows = []
        self._loaded = False
        self._search_debouncer = Debouncer(250, self.refresh, parent=self)
        self._build_ui()
        self._init_theme()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["lg"])

        self.toolbar = Toolbar()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("activities.search_placeholder"))
        self.search_input.setProperty("cssClass", "search")
        self.search_input.setMinimumWidth(240)
        self.search_input.textChanged.connect(self._search_debouncer.trigger)

        self.show_inactive_checkbox = QCheckBox(t("activities.show_inactive"))
        self.show_inactive_checkbox.stateChanged.connect(self.refresh)

        self.add_button = QPushButton(t("activities.add"))
        self.add_button.clicked.connect(self._on_add)

        self.toolbar.add_leading(self.search_input, stretch=1)
        self.toolbar.add_leading(self.show_inactive_checkbox)
        self.toolbar.add_trailing(self.add_button)

        root.addWidget(self.toolbar)

        self.table_card = SectionCard(title=t("activities.title"))

        self.table = make_standard_table(
            headers=[
                t("activities.col.name"),
                t("activities.col.days"),
                t("activities.col.subscriptions"),
                t("activities.col.status"),
                t("activities.col.color"),
            ],
            column_modes=["stretch", "stretch", "resize", "resize", "fixed"],
            parent=self,
        )
        self.table.setColumnWidth(4, 60)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.horizontalHeader().setFixedHeight(36)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.cellDoubleClicked.connect(lambda *_: self._on_edit())

        self.table_card.body.addWidget(self.table)

        self.empty_first_run = EmptyState(icon="🏃", message=t("activities.empty"), action_text=t("activities.add"), on_action=self._on_add)
        self.empty_first_run.hide()
        self.table_card.body.addWidget(self.empty_first_run)

        self.empty_no_results = EmptyState(icon="🔍", message=t("activities.no_results"))
        self.empty_no_results.hide()
        self.table_card.body.addWidget(self.empty_no_results)

        self.table_card.body.addSpacing(SPACING["sm"])

        action_row = QHBoxLayout()
        action_row.setSpacing(SPACING["sm"])

        self.toggle_button = QPushButton(t("activities.action.deactivate"))
        make_warning(self.toggle_button)  # Yellow
        self.toggle_button.clicked.connect(self._on_toggle_active)
        self.toggle_button.setEnabled(False)

        self.delete_button = QPushButton(t("activities.action.delete"))
        make_danger(self.delete_button)
        self.delete_button.clicked.connect(self._on_delete)
        self.delete_button.setEnabled(False)

        action_row.addStretch()
        action_row.addWidget(self.toggle_button)
        action_row.addWidget(self.delete_button)

        self.table_card.body.addLayout(action_row)
        root.addWidget(self.table_card, stretch=1)

    def restyle(self):
        tm = theme()
        self.table.setStyleSheet(
            f"QTableWidget {{"
            f"  selection-background-color: {tm.color('primary_soft')};"
            f"  selection-color: {tm.color('text')};"
            f"}}"
            f"QTableWidget::item:selected {{"
            f"  background-color: {tm.color('primary_soft')};"
            f"  color: {tm.color('text')};"
            f"}}"
            f"QTableWidget::item:hover:!selected {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"}}"
        )
        if hasattr(self, "_rows"):
            self._render_rows(self._rows)

    def refresh(self):
        # Always fetch all (including suspended). 
        # If show_inactive is unchecked, we'll still show them but with a suspended tag.
        all_acts = activity_service.list_all()

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

        has_any_color = any(a.color for a in activities)
        self.table.setColumnHidden(4, not has_any_color)

        show_inactive = self.show_inactive_checkbox.isChecked()

        for i, a in enumerate(activities):
            # If it's inactive and the checkbox is OFF, we still show it, 
            # but we can dim it to indicate it's suspended.
            is_suspended = not a.active
            
            name = f"{a.name_en} · {a.name_ar}"
            name_item = QTableWidgetItem(name)
            if is_suspended:
                name_item.setForeground(QColor(tm.color("text_secondary")))
            self.table.setItem(i, 0, name_item)

            days_str = ", ".join(t(f"weekday.{d.lower()}") for d in a.default_days)
            days_item = QTableWidgetItem(days_str)
            if is_suspended:
                days_item.setForeground(QColor(tm.color("text_secondary")))
            self.table.setItem(i, 1, days_item)

            active_count = activity_service.count_active_references(a.activity_id)
            count_item = QTableWidgetItem(str(active_count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_suspended:
                count_item.setForeground(QColor(tm.color("text_secondary")))
            self.table.setItem(i, 2, count_item)

            # Status
            if a.active:
                status_text = t("activities.status.active")
                color = tm.color("success")
                bg = tm.color("success_soft")
            else:
                status_text = t("activities.status.inactive") # Suspended
                color = tm.color("warning")
                bg = tm.color("warning_soft")

            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(QColor(color))
            status_item.setBackground(QColor(bg))
            self.table.setItem(i, 3, status_item)

            if has_any_color:
                color_item = QTableWidgetItem()
                if a.color:
                    color_item.setBackground(QColor(a.color))
                color_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
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
        self.delete_button.setEnabled(enabled)

        if a is None or a.active:
            self.toggle_button.setText(t("activities.action.deactivate"))
            make_warning(self.toggle_button)
        else:
            self.toggle_button.setText(t("activities.action.reactivate"))
            make_warning(self.toggle_button)

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

    def _on_delete(self):
        a = self._selected()
        if a is None:
            return
        if not ask(self, t("activities.confirm.delete_title"), t("activities.confirm.delete_msg", name=a.name_en)):
            return
        
        try:
            # Move to archive (Recycle Bin)
            from repositories import activities_repo
            activities_repo.archive(a.activity_id)
        except Exception as e:
            warn(self, t("activities.confirm.title"), str(e))
            return
            
        self.refresh()

    def _on_toggle_active(self):
        a = self._selected()
        if a is None:
            return

        if a.active:
            # Suspend (Soft-disable)
            refs = activity_service.count_references(a.activity_id)
            msg_key = "activities.confirm.deactivate_with_refs" if refs > 0 else "activities.confirm.deactivate"
            if not ask(self, t("activities.confirm.title"), t(msg_key, name=a.name_en, count=refs)):
                return
            activity_service.deactivate(a.activity_id)
        else:
            # Reactivate
            activity_service.reactivate(a.activity_id)

        self.refresh()