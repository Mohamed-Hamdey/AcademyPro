"""
License activation screen.

Shown before the login dialog if the app is unlicensed or the license
is invalid. Cannot be skipped — the user must import a valid license
file to proceed.
"""

import os
import sys

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QFileDialog, QApplication,
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap, QGuiApplication

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_academy_name, get_academy_logo, load_config
from services import license_service
from ui import i18n
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS, TYPOGRAPHY
from ui.i18n import t


class LicenseScreen(ThemedWidget, QDialog):
    """
    Modal license import screen. Blocks the app until a valid license
    is imported (or the user quits).
    """

    def __init__(self, status: license_service.LicenseStatus = None, parent=None):
        QDialog.__init__(self, parent)
        self._status = status or license_service.get_status()
        self.setWindowTitle(t("license.title"))
        self.setModal(True)
        self.setMinimumWidth(520)
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["2xl"], SPACING["xl"], SPACING["2xl"], SPACING["xl"]
        )
        layout.setSpacing(SPACING["md"])
        layout.addStretch()

        # Logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(80, 80)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_logo()
        layout.addWidget(self.logo_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Academy name
        self.academy_label = QLabel()
        self.academy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.academy_label.setWordWrap(True)
        layout.addWidget(self.academy_label)

        layout.addSpacing(SPACING["lg"])

        # Title
        self.title_label = QLabel(t("license.heading"))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        # Status / reason
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        layout.addSpacing(SPACING["md"])

        # Machine ID block
        mid_box = QFrame()
        mid_box.setObjectName("machineIdBox")
        mid_layout = QVBoxLayout(mid_box)
        mid_layout.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"]
        )
        mid_layout.setSpacing(4)

        mid_hint = QLabel(t("license.machine_id_hint"))
        mid_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mid_hint = mid_hint
        mid_layout.addWidget(mid_hint)

        self.machine_id_label = QLabel(self._status.machine_id)
        self.machine_id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.machine_id_label.setSelectableByMouse if False else None
        self.machine_id_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        mid_layout.addWidget(self.machine_id_label)

        self.copy_button = QPushButton(t("license.copy_machine_id"))
        make_secondary(self.copy_button)
        self.copy_button.clicked.connect(self._on_copy_machine_id)
        mid_layout.addWidget(self.copy_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.machine_id_box = mid_box
        layout.addWidget(mid_box)

        layout.addSpacing(SPACING["md"])

        # Actions
        action_row = QHBoxLayout()
        action_row.setSpacing(SPACING["sm"])

        self.import_button = QPushButton(t("license.import"))
        self.import_button.setDefault(True)
        self.import_button.setMinimumHeight(42)
        self.import_button.clicked.connect(self._on_import)

        self.quit_button = QPushButton(t("license.quit"))
        make_secondary(self.quit_button)
        self.quit_button.setMinimumHeight(42)
        self.quit_button.clicked.connect(self.reject)

        action_row.addWidget(self.quit_button)
        action_row.addWidget(self.import_button, stretch=1)
        layout.addLayout(action_row)

        layout.addStretch()

        # Populate text based on status
        self._refresh_text()

    def _load_logo(self):
        path = get_academy_logo()
        if path:
            pix = QPixmap(path).scaled(
                80, 80,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(pix)
        else:
            initials = "".join(w[0] for w in get_academy_name().split()[:3]).upper()
            self.logo_label.setText(initials or "A")

    def restyle(self):
        tm = theme()

        cfg = load_config()
        if i18n.current_language() == "ar":
            name = cfg.get("academy_name_ar") or cfg.get("academy_name", "")
        else:
            name = cfg.get("academy_name", "")
        self.academy_label.setText(name)
        self.academy_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['section']['size']}px;"
            f"  font-weight: 600;"
            f"}}"
        )

        if self.logo_label.pixmap() is None or self.logo_label.pixmap().isNull():
            self.logo_label.setStyleSheet(
                f"QLabel {{"
                f"  background-color: {tm.color('primary')};"
                f"  color: {tm.color('text_on_primary')};"
                f"  font-size: 28px; font-weight: 700;"
                f"  border-radius: {RADIUS['lg']}px;"
                f"}}"
            )

        self.title_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 16px;"
            f"  font-weight: 700;"
            f"}}"
        )

        self.status_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('danger')};"
            f"  background-color: {tm.color('danger_soft')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 10px 14px;"
            f"  font-size: 13px;"
            f"}}"
        )

        self.machine_id_box.setStyleSheet(
            f"QFrame#machineIdBox {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['md']}px;"
            f"}}"
        )
        self.mid_hint.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"}}"
        )
        self.machine_id_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 15px;"
            f"  font-weight: 700;"
            f"  font-family: 'Consolas', 'Courier New', monospace;"
            f"  padding: 4px;"
            f"}}"
        )

    def _refresh_text(self):
        s = self._status
        if s.valid:
            # Shouldn't happen — this screen only shows when unlicensed
            self.status_label.setText(t("license.status.valid"))
        else:
            reason_key = license_service.reason_message(s.reason)
            msg = t(reason_key)
            if s.reason == "expired" and s.license:
                msg = t("license.reason.expired_on",
                        date=s.license.expires)
            self.status_label.setText(msg)

    # ---------- actions ----------

    def _on_copy_machine_id(self):
        QApplication.clipboard().setText(self._status.machine_id)
        # Small visual feedback
        self.copy_button.setText(t("license.copied"))
        from qtpy.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.copy_button.setText(
            t("license.copy_machine_id")
        ))

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("license.pick_file_title"),
            "",
            t("license.file_filter"),
        )
        if not path:
            return

        new_status = license_service.import_license_file(path)
        self._status = new_status
        self._refresh_text()

        if new_status.valid:
            self.accept()
        # else: status label updates to show the new reason