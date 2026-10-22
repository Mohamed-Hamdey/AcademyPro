"""
Audit log screen — v5 (post-D1/D2/D3 rebuild).

Manager-only. Every recorded admin action, filtered by:
  * free-text search (username, action, target_type)
  * action type
  * user
  * date range

Layout:
    Toolbar (search + action + user + dates + reset)
    Table (stretch) — click a row to see full details in the panel below
    Detail panel (collapsible; visible only when a row is selected)
    Footer — "Showing X of Y rows · oldest … · retention 30d"
             [Export CSV] [Clear Log…]

Backing services (from D1):
    audit_service.query_ui(...)        — filtered rows + total + oldest
    audit_service.clear(reason)        — wipe + self-audit (R6)
    audit_service.purge_older_than(d)  — startup-only (called from main.py)
"""

import csv
import os
import sys
from datetime import date, datetime

from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QDateEdit, QTableWidgetItem, QFileDialog, QDialog,QTableWidget
    
)
from qtpy.QtCore import Qt, QDate,QTimer
from qtpy.QtGui import QColor, QFont

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import audit_repo
from services import audit_service
from config.config_loader import load_config
from ui.components import Toolbar, SectionCard, EmptyState,ghost_button
from ui.theme import theme, ThemedWidget, make_danger, make_secondary,make_ghost
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.table_helpers import make_standard_table
from ui.utils import Debouncer
from ui.message_box import ask, warn, info


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RETENTION_DAYS = 30
DEFAULT_LIMIT = 2000        # pulls 2000 most-recent rows for the table


# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------

class AuditScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._loaded = False
        self._dirty = True
        self._entries: list = []
        self._search_debouncer = Debouncer(250, self.refresh, parent=self)

        self._build_ui()
        self._init_theme()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if self._dirty:
            self._dirty = False
            self._loaded = True
            # Populate the filter dropdowns (actions + users) BEFORE
            # querying — otherwise they render empty on first open.
            self.reload_filter_options()
            self._clear_filters()
            QTimer.singleShot(0, self.refresh)
            self._update_reset_visibility()  
               # <-- NEW: reset all filters before refresh
# <-- add this

    def hideEvent(self, event):
        super().hideEvent(event)
        # Any other screen could have written new audit rows — re-read on
        # next show. Fixes the stale-data class of bug.
        self._dirty = True

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["md"])

        # ---------------- Filter bar ----------------
        self.toolbar = Toolbar()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("audit.search_placeholder"))
        self.search_input.setProperty("cssClass", "search")
        self.search_input.setMinimumWidth(240)
        self.search_input.textChanged.connect(self._search_debouncer.trigger)

        self.action_filter = QComboBox()
        self.action_filter.setMinimumWidth(180)
        self.action_filter.currentIndexChanged.connect(
            self._on_filter_changed
        )

        self.user_filter = QComboBox()
        self.user_filter.setMinimumWidth(140)
        self.user_filter.currentIndexChanged.connect(
            self._on_filter_changed
        )

        self.search_input.textChanged.connect(
            self._update_reset_visibility
        )

        self.user_filter = QComboBox()
        self.user_filter.setMinimumWidth(140)
        self.user_filter.currentIndexChanged.connect(self._on_filter_changed)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setFixedWidth(150)
        self.date_from.dateChanged.connect(self._on_filter_changed)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setFixedWidth(150)
        self.date_to.dateChanged.connect(self._on_filter_changed)

        self.reset_btn = QPushButton("↺  " + t("audit.clear_filters"))
        make_ghost(self.reset_btn)
        self.reset_btn.clicked.connect(self._clear_filters)
        self.reset_btn.hide()   # <-- add this: hidden until a filter is set

        self.toolbar.add_leading(self.search_input, stretch=1)
        self.toolbar.add_leading(self.action_filter)
        self.toolbar.add_leading(self.user_filter)

        date_row = QHBoxLayout()
        date_row.setSpacing(SPACING["sm"])
        date_row.addWidget(QLabel(t("audit.date_from")))
        date_row.addWidget(self.date_from)
        date_row.addWidget(QLabel(t("audit.date_to")))
        date_row.addWidget(self.date_to)
        date_row.addStretch()
        date_row.addWidget(self.reset_btn)

        root.addWidget(self.toolbar)
        root.addLayout(date_row)

        # ---------------- Table + detail split ----------------
        # Two vertical "cards" sharing the leftover space:
        #   * the table stretches to take most of it
        #   * the detail panel appears only when a row is selected
        self.table_card = SectionCard(title=t("audit.title"))
        self.table_card.body.setContentsMargins(0, 0, 0, 0)

        self.table = make_standard_table(
            headers=[
                t("audit.col.when"),
                t("audit.col.user"),
                t("audit.col.action"),
                t("audit.col.target"),
            ],
            column_modes=["resize", "resize", "resize", "stretch"],
            parent=self,
        )
        # Bigger default height — request #1 (larger table).
        # Bigger default height — request #1 (larger table).
        # FIX: Ensure the table scrolls instead of pushing the layout out.
        self.table.setMinimumHeight(400)   
        self.table.setSizePolicy(
            self.table.sizePolicy().horizontalPolicy(),
            self.table.sizePolicy().verticalPolicy().Expanding
        )
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)


        # The full details live in the panel below, not in a crammed
        # column. This is what makes the table breathe.
        self.table_card.body.addWidget(self.table)

        self.empty_state = EmptyState(
            icon="🗒",
            message=t("audit.empty"),
        )
        self.empty_state.hide()
        self.table_card.body.addWidget(self.empty_state)

        root.addWidget(self.table_card, stretch=1)



        # ---------------- Footer ----------------
        footer = QHBoxLayout()
        footer.setSpacing(SPACING["sm"])

        self.footer_label = QLabel("")
        footer.addWidget(self.footer_label)

        footer.addStretch()

        self.export_btn = QPushButton(t("audit.export.csv"))
        make_secondary(self.export_btn)
        self.export_btn.clicked.connect(self._on_export_csv)
        footer.addWidget(self.export_btn)

        self.clear_btn = QPushButton(t("audit.clear.button"))
        make_danger(self.clear_btn)
        self.clear_btn.clicked.connect(self._on_clear_log)
        footer.addWidget(self.clear_btn)

        root.addLayout(footer)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def restyle(self):
        tm = theme()

        # Table selection / hover colors — same pattern as other screens.
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

        # Footer is de-emphasized text.
        self.footer_label.setStyleSheet(
            f"color: {tm.color('text_secondary')}; font-size: 12px;"
        )



    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def refresh(self):
        search = self.search_input.text().strip()
        action = self.action_filter.currentData()
        username = self.user_filter.currentData()

        d_from = self.date_from.date()
        d_to = self.date_to.date()
        date_from = f"{d_from.year():04d}-{d_from.month():02d}-{d_from.day():02d}"
        date_to = f"{d_to.year():04d}-{d_to.month():02d}-{d_to.day():02d}"

        result = audit_service.query_ui(
            search=search,
            action=action,
            username=username,
            date_from=date_from,
            date_to=date_to,
            limit=DEFAULT_LIMIT,
        )

        self._entries = result["rows"]
        self._render_rows(self._entries)
        self._render_footer(result)


    def _render_rows(self, entries):
        if not entries:
            self.table.hide()
            self.empty_state.show()
            return

        self.table.show()
        self.empty_state.hide()

        # Block signals during re-populate so we don't fire
        # itemSelectionChanged mid-build.
        self.table.blockSignals(True)
        self.table.setRowCount(len(entries))
        tm = theme()

        for i, e in enumerate(entries):
            self.table.setItem(i, 0, QTableWidgetItem(e.created_at or ""))
            self.table.setItem(i, 1, QTableWidgetItem(e.username or ""))
            self.table.setItem(
                i, 2, QTableWidgetItem(self._friendly_action(e.action))
            )

            target = ""
            if e.target_type and e.target_id:
                target = f"{e.target_type} #{e.target_id}"
            elif e.target_type:
                target = e.target_type
            target_item = QTableWidgetItem(target)
            target_item.setForeground(QColor(tm.color("text_secondary")))
            self.table.setItem(i, 3, target_item)

            # Stash the AuditEntry so we can look it up on row click.
            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, id(e))

        self.table.blockSignals(False)

        # Cache the entry-by-id map for click lookup.
        self._by_identity = {id(e): e for e in entries}

    def _render_footer(self, result):
        shown = result.get("shown", 0)
        total = result.get("total", 0)
        oldest = result.get("oldest")
        retention = self._retention_days()

        oldest_str = (oldest[:10] if oldest else "—")
        retention_str = f"{retention}d" if retention else "—"

        self.footer_label.setText(
            t("audit.footer.showing", shown=shown, total=total)
            + "  ·  "
            + t("audit.footer.oldest", date=oldest_str)
            + "  ·  "
            + t("audit.footer.retention", days=retention_str)
        )

    def _retention_days(self) -> int:
        try:
            cfg = load_config() or {}
            return int(cfg.get("audit_retention_days", DEFAULT_RETENTION_DAYS))
        except Exception:
            return DEFAULT_RETENTION_DAYS

    # ------------------------------------------------------------------
    # Row selection → highlight + detail panel
    # ------------------------------------------------------------------

    def _on_row_selected(self):
        """Row click — just select (Qt does the highlight automatically).
        Nothing else to do now that the detail panel is gone."""
        return  # selection is handled by Qt; no side effects needed

    def _on_row_double_clicked(self, item):
        """Double-click — copy the full JSON details of the row to clipboard."""
        if item is None:
            return
        row_idx = item.row()
        if row_idx < 0 or row_idx >= len(self._entries):
            return

        entry = self._entries[row_idx]
        import json
        details_dict = entry.details_dict() if hasattr(entry, "details_dict") else {}
        payload = (
            f"when:    {entry.created_at or '—'}\n"
            f"user:    {entry.username or '—'}\n"
            f"action:  {entry.action}\n"
            f"target:  {entry.target_type or '—'}"
            f"{(' #' + str(entry.target_id)) if entry.target_id else ''}\n"
            f"details: {json.dumps(details_dict, ensure_ascii=False, indent=2)}"
        )
        from qtpy.QtWidgets import QApplication
        QApplication.clipboard().setText(payload)

        # Small visual confirmation via the footer (transient).
        self._show_footer_toast(t("audit.copied_toast"))

    def _show_footer_toast(self, message: str):
        """
        Briefly show a confirmation message in the footer, then restore
        the normal footer text. Simple, no extra widgets.
        """
        from qtpy.QtCore import QTimer
        # Save whatever was in the footer
        if not hasattr(self, "_footer_saved") or self._footer_saved is None:
            self._footer_saved = self.footer_label.text()

        self.footer_label.setText(message)
        self.footer_label.setStyleSheet(
            f"color: {theme().color('success')}; font-size: 12px;"
        )

        def _restore():
            self.footer_label.setText(self._footer_saved or "")
            self._footer_saved = None
            self.restyle()   # restore normal footer styling

        QTimer.singleShot(1800, _restore)

    # ------------------------------------------------------------------
    # Filter reset
    # ------------------------------------------------------------------

    def _clear_filters(self):
        """Restore all filter defaults and refresh exactly once."""
        try:
            self._search_debouncer.stop()
        except (AttributeError, RuntimeError):
            pass

        widgets = (
            self.search_input,
            self.action_filter,
            self.user_filter,
            self.date_from,
            self.date_to,
        )

        for widget in widgets:
            widget.blockSignals(True)

        try:
            self.search_input.clear()
            self.action_filter.setCurrentIndex(0)
            self.user_filter.setCurrentIndex(0)
            self.date_from.setDate(QDate.currentDate().addDays(-30))
            self.date_to.setDate(QDate.currentDate())
        finally:
            for widget in widgets:
                widget.blockSignals(False)

        self._update_reset_visibility()
        QTimer.singleShot(0, self.refresh)
        
        # ---------- filter state / reset visibility ----------

    def _has_active_filters(self) -> bool:
        if self.search_input.text().strip():
            return True
        if self.action_filter.currentData() is not None:
            return True
        if self.user_filter.currentData() is not None:
            return True
        # Date range: default is today → today - 30 days
        today = QDate.currentDate()
        default_from = today.addDays(-30)
        if self.date_from.date() != default_from:
            return True
        if self.date_to.date() != today:
            return True
        return False

    def _update_reset_visibility(self):
        if hasattr(self, "reset_btn"):
            self.reset_btn.setVisible(self._has_active_filters())

    def _on_filter_changed(self, *args):
        self._update_reset_visibility()
        QTimer.singleShot(0, self.refresh)
    # ------------------------------------------------------------------
    # Export CSV
    # ------------------------------------------------------------------

    def _on_export_csv(self):
        if not self._entries:
            info(self, t("audit.export.empty_title"), t("audit.export.empty_body"))
            return

        default_name = f"audit_log_{date.today().isoformat()}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("audit.export.dialog_title"),
            default_name,
            "CSV (*.csv)",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow([
                    t("audit.col.when"),
                    t("audit.col.user"),
                    t("audit.col.action"),
                    "code",
                    t("audit.col.target"),
                    t("audit.col.details"),
                ])
                for e in self._entries:
                    target = ""
                    if e.target_type and e.target_id:
                        target = f"{e.target_type} #{e.target_id}"
                    elif e.target_type:
                        target = e.target_type
                    import json
                    details_str = json.dumps(
                        e.details_dict() if hasattr(e, "details_dict") else {},
                        ensure_ascii=False,
                    )
                    w.writerow([
                        e.created_at or "",
                        e.username or "",
                        self._friendly_action(e.action),
                        e.action,
                        target,
                        details_str,
                    ])
            info(self, t("audit.export.done_title"),
                 t("audit.export.done_body", path=path, n=len(self._entries)))
        except Exception as ex:
            warn(self, t("audit.export.fail_title"), str(ex))

    # ------------------------------------------------------------------
    # Clear Log (typed-confirm, R6 self-audit baked in)
    # ------------------------------------------------------------------

    def _on_clear_log(self):
        dlg = _TypedConfirmDialog(
            self,
            t("audit.clear.confirm_title"),
            t("audit.clear.confirm_body"),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            result = audit_service.clear(reason="cleared from audit screen")
            info(
                self,
                t("audit.clear.success_title"),
                t("audit.clear.success_body", n=result["deleted"]),
            )
            # Force a full reload so the new single audit.clear row appears.
            self._dirty = True
            QTimer.singleShot(0, self.refresh)
        except Exception as ex:
            warn(self, t("audit.clear.fail_title"), str(ex))

    # ------------------------------------------------------------------
    # Friendly label
    # ------------------------------------------------------------------

    def _friendly_action(self, code: str) -> str:
        """
        Map an action code to a translated label. If no translation
        exists, humanize the code (e.g. `subscription.record_payment`
        → `Subscription Record Payment`) rather than showing a raw key.
        """
        key = f"audit.action.{code}"
        translated = t(key)
        if translated != key:
            return translated
        # Fallback: humanize the code.
        if not code:
            return "—"
        parts = code.replace(".", " ").replace("_", " ").split()
        return " ".join(p.capitalize() for p in parts)

    # ------------------------------------------------------------------
    # Filter-dropdown repopulation (called from MainWindow if it ever
    # needs to force the dropdowns to refresh after new actions appear)
    # ------------------------------------------------------------------

    def reload_filter_options(self):
        """Rebuild the action/user dropdowns from the DB, preserving the
        current selection when possible."""
        cur_action = self.action_filter.currentData()
        cur_user = self.user_filter.currentData()

        self.action_filter.blockSignals(True)
        self.user_filter.blockSignals(True)

        self.action_filter.clear()
        self.action_filter.addItem(t("audit.filter.all_actions"), None)
        for code in audit_repo.distinct_actions():
            self.action_filter.addItem(self._friendly_action(code), code)

        self.user_filter.clear()
        self.user_filter.addItem(t("audit.filter.all_users"), None)
        for uname in audit_repo.distinct_usernames():
            self.user_filter.addItem(uname, uname)

        # Restore selection.
        if cur_action is not None:
            idx = self.action_filter.findData(cur_action)
            if idx >= 0:
                self.action_filter.setCurrentIndex(idx)
        if cur_user is not None:
            idx = self.user_filter.findData(cur_user)
            if idx >= 0:
                self.user_filter.setCurrentIndex(idx)

        self.action_filter.blockSignals(False)
        self.user_filter.blockSignals(False)


# ---------------------------------------------------------------------------
# Typed-confirm dialog (matches the recycle bin one in look + behavior)
# ---------------------------------------------------------------------------

class _TypedConfirmDialog(ThemedWidget, QDialog):
    """
    Requires typing the literal word 'DELETE' (case-insensitive) to enable
    the confirm button. Same pattern the Recycle Bin uses.
    """

    def __init__(self, parent, title, body):
        QDialog.__init__(self, parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["md"])

        lbl = QLabel(body)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.input = QLineEdit()
        self.input.setPlaceholderText("DELETE")
        self.input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton(t("msg.cancel"))
        make_secondary(cancel)
        cancel.clicked.connect(self.reject)

        self.confirm_btn = QPushButton(t("audit.clear.button"))
        make_danger(self.confirm_btn)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel)
        btn_row.addWidget(self.confirm_btn)
        layout.addLayout(btn_row)

        self._init_theme()

    def _on_text_changed(self, text):
        self.confirm_btn.setEnabled(text.strip().upper() == "DELETE")