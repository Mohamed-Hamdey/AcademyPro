"""
Restore-from-backup dialog — v5 polish.

Shows the available backups (newest first), lets the manager pick one,
and calls backup_service.restore_backup() on confirm.

The caller (MainWindow) is responsible for telling the user to restart
after a successful restore — this dialog just closes with Accepted.

Design v5 polish:
  * Wider (780×560) for the backup list.
  * Warning-style hint banner at the top (destructive action reminder).
  * Divider between the hint and the list.
  * WA_DontShowOnScreen flash guard during construction.
"""

import os
from datetime import datetime

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QApplication, QFrame,
)
from qtpy.QtCore import Qt

from services import backup_service
from ui.components import EmptyState
from ui.theme import theme, ThemedWidget, make_secondary, make_danger
from ui.design import SPACING, RADIUS
from ui.i18n import t
from ui.message_box import ask, warn, error, info


def _col(name: str, fallback_token: str, default: str) -> str:
    """Resolve a theme colour without ever raising."""
    try:
        pal = theme().palette()
        return pal.get(name) or pal.get(fallback_token) or default
    except Exception:
        return default


class RestoreBackupDialog(ThemedWidget, QDialog):
    """
    Modal dialog listing backups. Returns Accepted if a restore was
    performed successfully.
    """

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)

        # Flash guard.
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setUpdatesEnabled(False)

        try:
            self.setWindowTitle(t("backup.restore.title"))
            self.setModal(True)
            self.setMinimumSize(780, 560)

            self._backups = []
            self._build_ui()
            self._reload()
            self._init_theme()
        finally:
            self.setUpdatesEnabled(True)
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
            self.update()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        # ---- Warning banner (destructive action) ----
        self.hint_label = QLabel(t("backup.restore.hint"), self)
        self.hint_label.setWordWrap(True)
        root.addWidget(self.hint_label)

        # ---- Divider ----
        divider = QFrame(self)
        divider.setObjectName("restoreDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            f"QFrame#restoreDivider {{"
            f"  background-color: {_col('divider', 'border', '#E8EDF3')};"
            f"  border: none;"
            f"}}"
        )
        root.addWidget(divider)

        # ---- List ----
        self.list_widget = QListWidget(self)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(lambda *_: self._on_restore())
        root.addWidget(self.list_widget, stretch=1)

        # ---- Empty state ----
        self.empty_state = EmptyState(
            icon="💾",
            message=t("backup.restore.empty"),
        )
        self.empty_state.hide()
        root.addWidget(self.empty_state, stretch=1)

        # ---- Footer buttons ----
        footer = QHBoxLayout()
        footer.setSpacing(SPACING["sm"])
        footer.setContentsMargins(0, SPACING["sm"], 0, 0)

        self.close_button = QPushButton(t("backup.btn.close"), self)
        make_secondary(self.close_button)
        self.close_button.clicked.connect(self.reject)

        self.restore_button = QPushButton(t("backup.btn.restore_selected"), self)
        make_danger(self.restore_button)
        self.restore_button.setEnabled(False)
        self.restore_button.clicked.connect(self._on_restore)

        footer.addStretch()
        footer.addWidget(self.close_button)
        footer.addWidget(self.restore_button)
        root.addLayout(footer)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _reload(self):
        self._backups = backup_service.list_backups()
        self.list_widget.clear()

        if not self._backups:
            self.list_widget.hide()
            self.empty_state.show()
            self.restore_button.setEnabled(False)
            return

        self.list_widget.show()
        self.empty_state.hide()

        for b in self._backups:
            text = self._format_row(b)
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, b["path"])
            # Dim pre-restore backups (they're internal safety copies).
            if b["label"] == "pre-restore":
                item.setForeground(Qt.GlobalColor.gray)
            self.list_widget.addItem(item)

    @staticmethod
    def _format_row(b: dict) -> str:
        size_kb = b["size"] / 1024
        try:
            when = datetime.fromtimestamp(b["mtime"]).strftime("%Y-%m-%d %H:%M")
        except Exception:
            when = "—"
        label = b["label"]
        return f"  {when}   ·   {size_kb:,.0f} KB   ·   {b['name']}   [{label}]"

    def _on_selection_changed(self):
        has_sel = bool(self.list_widget.selectedItems())
        self.restore_button.setEnabled(has_sel)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_restore(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        path = items[0].data(Qt.ItemDataRole.UserRole)
        if not path:
            return

        if not backup_service.verify_backup(path):
            error(
                self,
                t("backup.restore.invalid_title"),
                t("backup.restore.invalid_msg", name=os.path.basename(path)),
            )
            return

        # Confirmation — destructive.
        confirmed = ask(
            self,
            t("backup.restore.confirm_title"),
            t("backup.restore.confirm_msg", name=os.path.basename(path)),
        )
        if not confirmed:
            return

        ok = backup_service.restore_backup(path)
        if not ok:
            error(
                self,
                t("backup.restore.failed_title"),
                t("backup.restore.failed_msg"),
            )
            return

        info(
            self,
            t("backup.restore.done_title"),
            t("backup.restore.done_msg"),
        )
        self.accept()

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

    def restyle(self):
        tm = theme()

        # Warning banner (destructive action reminder).
        self.hint_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('warning')};"
            f"  background-color: {tm.color('warning_soft')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 10px 14px;"
            f"  font-weight: 600;"
            f"  font-size: 12px;"
            f"}}"
        )

        # List styling (kept as before, but now on the widget itself).
        self.list_widget.setStyleSheet(
            f"QListWidget {{"
            f"  background-color: {tm.color('surface')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: 6px;"
            f"  padding: 4px;"
            f"  outline: none;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 8px 10px;"
            f"  color: {tm.color('text')};"
            f"  border-radius: 4px;"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background-color: {tm.color('primary_soft')};"
            f"}}"
        )