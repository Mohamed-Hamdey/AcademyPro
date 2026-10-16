"""QR preview dialog — v4 design."""

import os
import sys
import shutil

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFileDialog,
    QFrame,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ui.message_box import info
from ui.components import Pill
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS
from ui.i18n import t


class QRPreviewDialog(ThemedWidget, QDialog):
    def __init__(self, player_name, player_id, qr_path, parent=None):
        QDialog.__init__(self, parent)
        self.qr_path = qr_path
        self.player_name = player_name
        self.setWindowTitle(t("dlg.qr.title"))
        self.setMinimumWidth(360)
        self._build_ui(player_id)
        self._init_theme()

    def _build_ui(self, player_id):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        # Header: name + ID + created pill
        self.title = QLabel(self.player_name)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        header_row = QHBoxLayout()
        self.id_label = QLabel(t("dlg.qr.player_id", player_id=player_id))
        header_row.addWidget(self.id_label)
        header_row.addStretch()
        self.success_pill = Pill(t("dlg.qr.created_badge"), "success")
        header_row.addWidget(self.success_pill)
        layout.addLayout(header_row)

        # QR code in a soft frame
        qr_frame = QFrame()
        qr_frame.setObjectName("qrFrame")
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(self.qr_path).scaled(
            220, 220, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.qr_label.setPixmap(pixmap)
        qr_layout.addWidget(self.qr_label)
        self.qr_frame = qr_frame
        layout.addWidget(qr_frame)

        self.hint = QLabel(t("dlg.qr.hint"))
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        self.save_as_button = QPushButton(t("dlg.qr.save_as"))
        self.close_button = QPushButton(t("dlg.qr.done"))
        make_secondary(self.save_as_button)
        self.save_as_button.clicked.connect(self._on_save_as)
        self.close_button.clicked.connect(self.accept)
        button_row.addWidget(self.save_as_button)
        button_row.addStretch()
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

    def restyle(self):
        tm = theme()
        self.title.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 18px;"
            f"  font-weight: 700;"
            f"}}"
        )
        self.id_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
        )
        self.qr_frame.setStyleSheet(
            f"QFrame#qrFrame {{"
            f"  background-color: {tm.color('surface_alt')};"
            f"  border: 1px solid {tm.color('border')};"
            f"  border-radius: {RADIUS['lg']}px;"
            f"}}"
        )
        self.hint.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-style: italic;"
            f"  font-size: 12px;"
            f"}}"
        )

    def _on_save_as(self):
        default_name = f"{self.player_name.replace(' ', '_')}_QR.png"
        dest_path, _ = QFileDialog.getSaveFileName(
            self, t("dlg.qr.save_dialog_title"), default_name, t("dlg.qr.png_filter")
        )
        if dest_path:
            shutil.copy(self.qr_path, dest_path)
            info(
                self, t("dlg.qr.saved_title"),
                t("dlg.qr.saved_msg", path=dest_path),
            )