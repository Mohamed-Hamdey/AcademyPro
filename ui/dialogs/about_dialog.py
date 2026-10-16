"""
About dialog.

Shows the academy logo, version, runtime info, activation status, and
a few support buttons. Reachable from the user menu.

The "Third-party licenses" section will be filled in as part of a later
task — for now it's a placeholder label so the dialog has a slot for it.
"""

import os
import sys
import platform
from datetime import datetime

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QApplication, QGridLayout,
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap, QGuiApplication

from config.config_loader import get_academy_name, get_academy_logo, load_config
from paths import AppPaths, bundled_path
from services import license_service
from ui import i18n
from ui.theme import theme, ThemedWidget, make_secondary
from ui.design import SPACING, RADIUS, TYPOGRAPHY
from ui.i18n import t
from ui.message_box import info
from version import __version__, APP_NAME

class AboutDialog(ThemedWidget, QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(t("about.title"))
        self.setModal(True)
        self.setMinimumWidth(520)
        self._build_ui()
        self._init_theme()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        # ---- Logo + academy name + version ----
        header = QHBoxLayout()
        header.setSpacing(SPACING["md"])

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(72, 72)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_logo()
        header.addWidget(self.logo_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        self.academy_label = QLabel()
        self.academy_label.setWordWrap(True)
        title_col.addWidget(self.academy_label)

        self.app_name_label = QLabel(APP_NAME)
        title_col.addWidget(self.app_name_label)

        self.version_label = QLabel(t("about.version", version=__version__))
        title_col.addWidget(self.version_label)

        title_col.addStretch()
        header.addLayout(title_col, stretch=1)
        root.addLayout(header)

        # ---- Divider ----
        root.addWidget(self._make_hr())

        # ---- Info grid ----
        grid = QGridLayout()
        grid.setHorizontalSpacing(SPACING["md"])
        grid.setVerticalSpacing(6)

        row = 0
        self._add_info_row(grid, row, t("about.label.runtime"),
                           self._runtime_string())
        row += 1

        self._add_info_row(grid, row, t("about.label.activation"),
                           self._activation_string())
        row += 1

        self._add_info_row(grid, row, t("about.label.machine_id"),
                           self._machine_id_string())
        row += 1

        self._add_info_row(grid, row, t("about.label.data_folder"),
                           AppPaths.data_root())

        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

        # ---- Divider ----
        root.addWidget(self._make_hr())

        # ---- Third-party licenses summary + link ----
        licenses_row = QHBoxLayout()
        licenses_row.setSpacing(SPACING["sm"])

        self.licenses_label = QLabel(t("about.licenses.summary"))
        self.licenses_label.setWordWrap(True)
        licenses_row.addWidget(self.licenses_label, stretch=1)

        self.view_licenses_button = QPushButton(t("about.btn.view_licenses"))
        make_secondary(self.view_licenses_button)
        self.view_licenses_button.clicked.connect(self._on_view_licenses)
        licenses_row.addWidget(self.view_licenses_button)

        root.addLayout(licenses_row)

        # ---- Buttons ----
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])

        self.copy_button = QPushButton(t("about.btn.copy_diag"))
        make_secondary(self.copy_button)
        self.copy_button.clicked.connect(self._on_copy_diagnostics)

        self.open_logs_button = QPushButton(t("about.btn.open_logs"))
        make_secondary(self.open_logs_button)
        self.open_logs_button.clicked.connect(self._on_open_logs)

        self.close_button = QPushButton(t("about.btn.close"))
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.accept)

        button_row.addWidget(self.copy_button)
        button_row.addWidget(self.open_logs_button)
        button_row.addStretch()
        button_row.addWidget(self.close_button)
        root.addLayout(button_row)

    def _add_info_row(self, grid, row, key, value):
        key_label = QLabel(key)
        key_label.setObjectName("aboutKey")
        value_label = QLabel(value)
        value_label.setObjectName("aboutValue")
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        grid.addWidget(key_label, row, 0)
        grid.addWidget(value_label, row, 1)

    def _make_hr(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setObjectName("aboutHR")
        return line

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _load_logo(self):
        path = get_academy_logo()
        if path and os.path.exists(path):
            pix = QPixmap(path).scaled(
                72, 72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(pix)
        else:
            initials = "".join(
                w[0] for w in get_academy_name().split()[:3]
            ).upper() or "A"
            self.logo_label.setText(initials)

    def _runtime_string(self) -> str:
        try:
            import qtpy
            from qtpy import API_NAME
            qt_binding = f"{API_NAME}"
            try:
                import PySide6
                qt_ver = PySide6.__version__
            except Exception:
                qt_ver = "?"
        except Exception:
            qt_binding = "qtpy"
            qt_ver = "?"

        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return f"Python {py_ver}  ·  {qt_binding} {qt_ver}"

    def _activation_string(self) -> str:
        try:
            status = license_service.get_status()
            if status.valid:
                if getattr(status, "expires_on", None):
                    return t("about.activation.active_until",
                             date=status.expires_on)
                return t("about.activation.active")
            return t("about.activation.inactive",
                     reason=getattr(status, "reason", ""))
        except Exception:
            return "—"

    def _machine_id_string(self) -> str:
        try:
            return license_service.machine_id()
        except Exception:
            return "—"

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_copy_diagnostics(self):
        text = self._build_diagnostics_text()
        cb = QGuiApplication.clipboard()
        cb.setText(text)
        info(self, t("about.copied.title"), t("about.copied.body"))

    def _build_diagnostics_text(self) -> str:
        lines = [
            f"{APP_NAME}  v{__version__}",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            f"Python:      {sys.version.split()[0]}",
            f"Platform:    {platform.platform()}",
        ]
        try:
            from qtpy import API_NAME
            lines.append(f"Qt binding:  {API_NAME}")
        except Exception:
            pass
        try:
            import PySide6
            lines.append(f"PySide6:     {PySide6.__version__}")
        except Exception:
            pass

        try:
            cfg = load_config()
            lines.append(f"Academy (en): {cfg.get('academy_name', '')}")
            lines.append(f"Academy (ar): {cfg.get('academy_name_ar', '')}")
        except Exception:
            pass

        try:
            status = license_service.get_status()
            lines.append(f"License valid: {status.valid}")
            if getattr(status, "reason", None):
                lines.append(f"License reason: {status.reason}")
        except Exception:
            pass

        lines.append(f"Data folder: {AppPaths.data_root()}")
        lines.append(f"Database:    {AppPaths.database()}")
        lines.append(f"Log folder:  {AppPaths.logs_dir()}")

        try:
            from ui import i18n as _i18n
            lines.append(f"Language:    {_i18n.current_language()}")
        except Exception:
            pass

        try:
            from ui.theme import theme as _theme
            lines.append(f"Theme mode:  {_theme().mode}")
        except Exception:
            pass

        return "\n".join(lines)

    def _on_open_logs(self):
        path = AppPaths.logs_dir()
        try:
            # Windows
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            info(self, t("about.open_logs.failed_title"),
                 t("about.open_logs.failed_body", path=path))
    def _on_view_licenses(self):
        """
        Open LICENSES.txt in the system's default text editor.

        In a frozen build it lives next to the .exe (bundled by
        PyInstaller via the spec's `datas`). In source mode it's at the
        project root.
        """
        candidates = [
            bundled_path("LICENSES.txt"),          # frozen build
            os.path.join(os.path.dirname(__file__), "..", "..", "LICENSES.txt"),
        ]
        for path in candidates:
            path = os.path.abspath(path)
            if os.path.exists(path):
                try:
                    if sys.platform.startswith("win"):
                        os.startfile(path)
                    elif sys.platform == "darwin":
                        import subprocess
                        subprocess.Popen(["open", path])
                    else:
                        import subprocess
                        subprocess.Popen(["xdg-open", path])
                    return
                except Exception as e:
                    info(self,
                         t("about.open_licenses.failed_title"),
                         t("about.open_licenses.failed_body", path=path))
                    return
        info(self,
             t("about.open_licenses.missing_title"),
             t("about.open_licenses.missing_body"))
    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

    def restyle(self):
        tm = theme()

        # Logo monogram background (if no image)
        if self.logo_label.pixmap() is None or self.logo_label.pixmap().isNull():
            self.logo_label.setStyleSheet(
                f"QLabel {{"
                f"  background-color: {tm.color('primary')};"
                f"  color: {tm.color('text_on_primary')};"
                f"  font-size: 28px; font-weight: 700;"
                f"  border-radius: {RADIUS['md']}px;"
                f"}}"
            )

        cfg = load_config()
        if i18n.current_language() == "ar":
            academy = cfg.get("academy_name_ar") or cfg.get("academy_name", "")
        else:
            academy = cfg.get("academy_name", "")
        self.academy_label.setText(academy)

        self.academy_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: {TYPOGRAPHY['section']['size']}px;"
            f"  font-weight: 700;"
            f"}}"
        )
        self.app_name_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
        )
        self.version_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('primary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"}}"
        )
        self.licenses_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 11px;"
            f"}}"
        )

        # Style the info grid labels via object names
        for lbl in self.findChildren(QLabel, "aboutKey"):
            lbl.setStyleSheet(
                f"QLabel#aboutKey {{"
                f"  color: {tm.color('text_secondary')};"
                f"  background-color: transparent;"
                f"  font-size: 12px;"
                f"  font-weight: 600;"
                f"}}"
            )
        for lbl in self.findChildren(QLabel, "aboutValue"):
            lbl.setStyleSheet(
                f"QLabel#aboutValue {{"
                f"  color: {tm.color('text')};"
                f"  background-color: transparent;"
                f"  font-size: 12px;"
                f"}}"
            )
        for line in self.findChildren(QFrame, "aboutHR"):
            line.setStyleSheet(
                f"QFrame#aboutHR {{ background-color: {tm.color('divider')};"
                f" border: none; }}"
            )