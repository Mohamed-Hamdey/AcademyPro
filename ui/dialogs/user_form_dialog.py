"""
Add / edit user dialog — v5 design.

Create mode:
    Photo preview + buttons, Username, Display name, Password + confirm, Role

Edit mode:
    Photo preview + buttons, Username (read-only), Display name, Role, Active

What changed from v4 (logic and audit calls are unchanged):
  * Round avatar preview (the chosen photo, or the user's initial) instead of
    a bare filename label; "Remove photo" button.
  * Role is a segmented control instead of a combo box.
  * Show/hide button inside the password fields.
  * The "last manager" notice is a real banner at the top (not inserted into
    the layout at runtime).
  * No inline stylesheets for the read-only username; theme.py v4.2 styles it.
  * New translation key: users.dialog.remove_photo
      ar: "إزالة الصورة"   en: "Remove photo"
"""

import os
import sys
import logging

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QHBoxLayout, QLabel, QFileDialog, QCheckBox, QButtonGroup,
    QWidget, QFrame, QSizePolicy,
)
from qtpy.QtCore import Qt, QRectF, QSize, QPointF
from qtpy.QtGui import (
    QAction, QPainter, QPainterPath, QPixmap, QColor, QPen, QBrush, QTextOption,
    QFont, QIcon,
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from repositories import users_repo
from services import audit_service, auth_service
from ui.theme import theme, ThemedWidget, make_secondary, make_ghost, make_segment
from ui.design import SPACING, RADIUS
from ui import i18n
from ui.i18n import t
from paths import AppPaths


# Logical role order. Labels stay bilingual, exactly as before.
_ROLES = (
    ("manager", "المدير · Manager"),
    ("receptionist", "موظف الاستقبال · Receptionist"),
)

_AVATAR_COLORS = ("#2563EB", "#16A34A", "#9333EA", "#EA580C", "#0D9488")


def _col(name: str, fallback_token: str, default: str) -> QColor:
    """Resolve a theme colour without ever raising."""
    try:
        pal = theme().palette()
        return QColor(pal.get(name) or pal.get(fallback_token) or default)
    except Exception:
        return QColor(default)


def _hex(name: str, fallback_token: str, default: str) -> str:
    return _col(name, fallback_token, default).name()


def _tr(key: str, ar: str, en: str) -> str:
    """t(key), but fall back to a built-in string while the key is missing."""
    text = t(key)
    if text == key:
        return ar if i18n.current_language() == "ar" else en
    return text


def _eye_icon(revealed: bool, color: QColor) -> QIcon:
    """
    Eye icon for the password show/hide button. QLineEdit action buttons only
    draw an ICON (never text), so an emoji-text action renders as nothing.
    Open eye = password visible; slashed eye = password hidden.
    """
    size, scale = 20, 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(QColor(0, 0, 0, 0))
    pm.setDevicePixelRatio(scale)
    painter = QPainter(pm)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(color, 1.6, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        eye = QPainterPath()
        eye.moveTo(2.5, 10.0)
        eye.quadTo(10.0, 2.0, 17.5, 10.0)
        eye.quadTo(10.0, 18.0, 2.5, 10.0)
        painter.drawPath(eye)

        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(10.0, 10.0), 2.6, 2.6)

        if not revealed:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(QPointF(4.0, 16.0), QPointF(16.0, 4.0))
    finally:
        painter.end()
    return QIcon(pm)


class _FieldLabel(QWidget):
    """
    Form label with a separate red asterisk for required fields.

    The asterisk is its own QLabel instead of a "*" glued onto the translated
    text. A trailing "*" in an Arabic string is a bidi-neutral character, so it
    jumps to the wrong side and collides with / clips the last letter. With two
    widgets in a layout, Qt mirrors them correctly in RTL: text at the start,
    asterisk right after it.
    """

    def __init__(self, text: str, required: bool = True, parent=None):
        QWidget.__init__(self, parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        # Strip any "*" already present in the translation.
        self.text_lbl = QLabel((text or "").rstrip(" *"), self)
        lay.addWidget(self.text_lbl)

        self.star_lbl = None
        if required:
            self.star_lbl = QLabel("*", self)
            lay.addWidget(self.star_lbl)
        lay.addStretch(1)
        self.apply_theme()

    def apply_theme(self):
        if self.star_lbl is not None:
            self.star_lbl.setStyleSheet(
                f"QLabel {{ color: {_hex('danger', 'danger', '#DC2626')};"
                f" font-weight: 700; background: transparent; }}"
            )


# ---------------------------------------------------------------------------
# Round avatar preview
# ---------------------------------------------------------------------------

class _AvatarPreview(QWidget):
    """Circular preview: the chosen photo, or a coloured disc with the initial."""

    def __init__(self, size: int = 76, parent=None):
        QWidget.__init__(self, parent)
        self._size = size
        self._pixmap = None
        self._scaled = None
        self._text = "?"
        self._color = QColor(_AVATAR_COLORS[0])
        self.setFixedSize(size, size)

    def set_name(self, name: str):
        name = (name or "").strip()
        self._text = name[:1].upper() if name else "?"
        idx = (sum(ord(ch) for ch in name) % len(_AVATAR_COLORS)) if name else 0
        self._color = QColor(_AVATAR_COLORS[idx])
        self.update()

    def set_photo(self, path):
        pm = None
        if path and os.path.exists(path):
            loaded = QPixmap(path)
            if not loaded.isNull():
                pm = loaded
        self._pixmap = pm
        self._scaled = None
        self.update()

    def paintEvent(self, event):
        s = float(self._size)
        inset = 2.0
        d = s - 2 * inset
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            circle = QRectF(inset, inset, d, d)
            clip = QPainterPath()
            clip.addEllipse(circle)
            painter.setClipPath(clip)

            if self._pixmap is not None:
                if self._scaled is None:
                    self._scaled = self._pixmap.scaled(
                        QSize(int(d), int(d)),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                x = int(inset + (d - self._scaled.width()) / 2)
                y = int(inset + (d - self._scaled.height()) / 2)
                painter.drawPixmap(x, y, self._scaled)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self._color))
                painter.drawEllipse(circle)
                font = QFont(self.font())
                font.setPixelSize(max(12, int(s * 0.42)))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(circle, self._text, QTextOption(Qt.AlignmentFlag.AlignCenter))

            painter.setClipping(False)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(_col("border", "border", "#DCE3EC"), 2))
            painter.drawEllipse(circle)
        finally:
            painter.end()


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class UserFormDialog(ThemedWidget, QDialog):
    def __init__(self, user=None, is_last_manager=False, parent=None):
        QDialog.__init__(self, parent)
        self.editing_user = user
        self.is_last_manager = is_last_manager
        self.setWindowTitle(
            t("users.dialog.title_edit") if user else t("users.dialog.title_add")
        )
        self.setMinimumWidth(500)
        self._selected_photo_path = user.photo_path if user else None

        self._build_ui()
        if user:
            self._prefill(user)

        self._refresh_photo_widgets()
        self._init_theme()

        (self.display_name_input if user else self.username_input).setFocus()

    # ---------- UI ----------

    def _build_ui(self):
        self._reveal_actions = []
        self._field_labels = []

        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        # ---- "Last manager" banner (shown only in _prefill when relevant) ----
        self.hint_label = QLabel("", self)
        self.hint_label.setWordWrap(True)
        self.hint_label.hide()
        root.addWidget(self.hint_label)

        # ---- Profile row: avatar preview + photo buttons ----
        profile = QHBoxLayout()
        profile.setSpacing(SPACING["lg"])
        profile.setContentsMargins(0, 0, 0, 0)

        self.avatar = _AvatarPreview(76, self)

        side = QVBoxLayout()
        side.setSpacing(SPACING["sm"])
        photo_buttons = QHBoxLayout()
        photo_buttons.setSpacing(SPACING["sm"])
        photo_buttons.setContentsMargins(0, 0, 0, 0)

        self.choose_photo_btn = QPushButton(t("users.dialog.choose_photo"), self)
        make_secondary(self.choose_photo_btn)
        self.choose_photo_btn.clicked.connect(self._choose_photo)

        self.remove_photo_btn = QPushButton(_tr("users.dialog.remove_photo", "إزالة الصورة", "Remove photo"), self)
        make_ghost(self.remove_photo_btn)
        self.remove_photo_btn.clicked.connect(self._remove_photo)

        photo_buttons.addWidget(self.choose_photo_btn)
        photo_buttons.addWidget(self.remove_photo_btn)
        photo_buttons.addStretch()

        self.photo_label = QLabel(t("users.dialog.no_photo"), self)

        side.addStretch(1)
        side.addLayout(photo_buttons)
        side.addWidget(self.photo_label)
        side.addStretch(1)

        profile.addWidget(self.avatar)
        profile.addLayout(side, 1)
        root.addLayout(profile)

        # ---- Divider ----
        self.divider = QFrame(self)
        self.divider.setObjectName("userFormDivider")
        self.divider.setFixedHeight(1)
        root.addWidget(self.divider)

        # ---- Form ----
        form = QFormLayout()
        form.setSpacing(SPACING["sm"])
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.username_input = QLineEdit(self)
        self.display_name_input = QLineEdit(self)
        self.display_name_input.textChanged.connect(self._on_name_changed)
        self.username_input.textChanged.connect(self._on_name_changed)

        # Password fields (create mode only), with a show/hide button inside
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._add_reveal_toggle(self.password_input)
        self.password_confirm_input = QLineEdit(self)
        self.password_confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._add_reveal_toggle(self.password_confirm_input)
        if self.editing_user:
            # Not placed in the form in edit mode. They are children of the
            # dialog, so without hide() they would float at its top-left corner.
            self.password_input.hide()
            self.password_confirm_input.hide()

        # Role: segmented control. Least privilege by default in create mode.
        self.role_group = QButtonGroup(self)
        self.role_group.setExclusive(True)
        role_container = QWidget(self)
        role_row = QHBoxLayout(role_container)
        role_row.setContentsMargins(0, 0, 0, 0)
        role_row.setSpacing(SPACING["sm"])
        self._role_buttons = {}
        for role_key, label in _ROLES:
            btn = QPushButton(label, role_container)
            btn.setCheckable(True)
            make_segment(btn)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.role_group.addButton(btn)
            role_row.addWidget(btn, 1)
            self._role_buttons[role_key] = btn
        self._role_buttons["receptionist"].setChecked(True)

        # Active checkbox (edit mode only)
        self.active_checkbox = QCheckBox(t("users.dialog.active_label"), self)
        if not self.editing_user:
            # Edit mode only. Same reason as above: hide the unplaced child.
            self.active_checkbox.hide()

        def add_row(key, widget):
            label = _FieldLabel(t(key), True, self)
            self._field_labels.append(label)
            form.addRow(label, widget)

        add_row("users.dialog.username", self.username_input)
        add_row("users.dialog.display_name", self.display_name_input)

        if not self.editing_user:
            add_row("users.dialog.password", self.password_input)
            add_row("users.dialog.password_confirm", self.password_confirm_input)

        add_row("users.dialog.role", role_container)
        root.addLayout(form)

        if self.editing_user:
            root.addWidget(self.active_checkbox)

        # ---- Error banner ----
        self.error_label = QLabel("", self)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

        # ---- Buttons ----
        button_row = QHBoxLayout()
        button_row.setSpacing(SPACING["sm"])
        button_row.setContentsMargins(0, SPACING["sm"], 0, 0)

        cancel_button = QPushButton(t("users.dialog.cancel"), self)
        make_secondary(cancel_button)

        save_button = QPushButton(t("users.dialog.save"), self)
        save_button.setDefault(True)

        save_button.clicked.connect(self._on_save)
        cancel_button.clicked.connect(self.reject)

        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        root.addLayout(button_row)

    def _add_reveal_toggle(self, line: QLineEdit):
        action = QAction(line)

        def toggle(_checked=False):
            hidden = line.echoMode() == QLineEdit.EchoMode.Password
            line.setEchoMode(
                QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password
            )
            self._update_reveal_icon(line, action)

        action.triggered.connect(toggle)
        line.addAction(action, QLineEdit.ActionPosition.TrailingPosition)
        self._reveal_actions.append((line, action))
        self._update_reveal_icon(line, action)

    def _update_reveal_icon(self, line: QLineEdit, action: QAction):
        revealed = line.echoMode() == QLineEdit.EchoMode.Normal
        action.setIcon(_eye_icon(revealed, _col("text_secondary", "text_secondary", "#64748B")))

    # ---------- role helpers ----------

    def _selected_role(self) -> str:
        return "manager" if self._role_buttons["manager"].isChecked() else "receptionist"

    def _set_role(self, role: str):
        btn = self._role_buttons.get(role) or self._role_buttons["receptionist"]
        btn.setChecked(True)

    # ---------- theming ----------

    def restyle(self):
        tm = theme()
        self.photo_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
        )
        self.error_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('danger')};"
            f"  background-color: {tm.color('danger_soft')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 8px 12px;"
            f"}}"
        )
        self.hint_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {tm.color('warning')};"
            f"  background-color: {tm.color('warning_soft')};"
            f"  border-radius: {RADIUS['sm']}px;"
            f"  padding: 8px 12px;"
            f"  font-weight: 600;"
            f"}}"
        )
        self.divider.setStyleSheet(
            f"QFrame#userFormDivider {{"
            f"  background-color: {_hex('divider', 'border', '#E8EDF3')};"
            f"  border: none;"
            f"}}"
        )
        for label in self._field_labels:
            label.apply_theme()
        for line, action in self._reveal_actions:
            self._update_reveal_icon(line, action)
        self.avatar.update()

    # ---------- prefill ----------

    def _prefill(self, user):
        self.username_input.setText(user.username)
        self.username_input.setReadOnly(True)   # styled by theme.py (:read-only)
        self.display_name_input.setText(user.display_name)

        self._set_role(user.role)
        self.active_checkbox.setChecked(user.active)

        # If this user is the last active manager, lock the role and the
        # active checkbox — the app can't afford to lose them.
        if self.is_last_manager:
            self.active_checkbox.setChecked(True)
            self.active_checkbox.setEnabled(False)
            self._set_role("manager")
            for btn in self._role_buttons.values():
                btn.setEnabled(False)
            self.hint_label.setText(t("users.dialog.last_manager_hint"))
            self.hint_label.show()

    # ---------- photo ----------

    def _on_name_changed(self, _text=""):
        name = self.display_name_input.text().strip() or self.username_input.text().strip()
        self.avatar.set_name(name)

    def _refresh_photo_widgets(self):
        self._on_name_changed()
        self.avatar.set_photo(self._selected_photo_path)
        if self._selected_photo_path:
            self.photo_label.setText(os.path.basename(self._selected_photo_path))
        else:
            self.photo_label.setText(t("users.dialog.no_photo"))
        self.remove_photo_btn.setEnabled(bool(self._selected_photo_path))

    def _choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("users.dialog.select_photo_title"), "",
            t("dlg.player.images_filter")
        )
        if path:
            self._selected_photo_path = path
            self._refresh_photo_widgets()

    def _remove_photo(self):
        self._selected_photo_path = None
        self._refresh_photo_widgets()

    def _persist_photo(self, chosen_path, username: str):
        """Copy the chosen photo into the app's data folder, return the new path."""
        if not chosen_path:
            return None
        import shutil
        import time

        photos_dir = AppPaths.photos_dir()
        try:
            chosen_abs = os.path.abspath(chosen_path)
            if chosen_abs.startswith(os.path.abspath(photos_dir)):
                return chosen_path
        except Exception:
            pass

        ext = os.path.splitext(chosen_path)[1] or ".jpg"
        filename = f"user_{username}_{int(time.time() * 1000)}{ext}"
        dest = os.path.join(photos_dir, filename)
        try:
            shutil.copy2(chosen_path, dest)
            return dest
        except Exception as e:
            logging.getLogger(__name__).exception("Could not copy user photo: %s", e)
            return chosen_path

    # ---------- save ----------

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()

    def _on_save(self):
        self.error_label.hide()

        username = self.username_input.text().strip()
        display_name = self.display_name_input.text().strip()
        role = self._selected_role()

        if not display_name:
            self._show_error(t("users.dialog.error.display_name_required"))
            return

        # ---- Edit mode ----
        if self.editing_user:
            # Last-manager safety (belt and braces — dialog also locks the fields)
            if self.is_last_manager and role != "manager":
                self._show_error(t("users.error.last_manager_msg"))
                return

            photo_path = self._persist_photo(
                self._selected_photo_path, self.editing_user.username
            ) if self._selected_photo_path != self.editing_user.photo_path \
              else self.editing_user.photo_path

            updated = self.editing_user
            updated.display_name = display_name
            updated.role = role
            updated.active = self.active_checkbox.isChecked()
            updated.photo_path = photo_path

            try:
                users_repo.update(updated)
                audit_service.user_updated(
                    user_id=updated.user_id,
                    username=updated.username,
                    changes={
                        "display_name": updated.display_name,
                        "role": updated.role,
                        "active": updated.active,
                    },
                )
            except Exception as e:
                self._show_error(str(e))
                return

            self.accept()
            return

        # ---- Create mode ----
        password = self.password_input.text()
        password_confirm = self.password_confirm_input.text()

        if not username:
            self._show_error(t("users.dialog.error.username_required"))
            return
        if not password:
            self._show_error(t("users.dialog.error.password_required"))
            return
        if password != password_confirm:
            self._show_error(t("users.dialog.error.password_mismatch"))
            return
        if len(password) < 4:
            self._show_error(t("users.dialog.error.password_too_short"))
            return

        photo_path = self._persist_photo(self._selected_photo_path, username)

        try:
            new_user_id = auth_service.create_user(
                username=username,
                display_name=display_name,
                password=password,
                role=role,
                photo_path=photo_path,
            )
        except Exception as e:
            self._show_error(str(e))
            return

        audit_service.user_created(user_id=new_user_id, username=username)

        self.accept()