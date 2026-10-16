"""
Application entry point.

Startup order: QApplication -> language/theme -> splash -> DB init ->
license check -> login -> MainWindow.
"""

import os
# Force qtpy to use PySide6 (LGPL) instead of PyQt6 (GPL).
# Must be set BEFORE any Qt import.
os.environ.setdefault("QT_API", "pyside6")

import sys

from qtpy.QtWidgets import QApplication, QDialog
from qtpy.QtCore import Qt, QSettings


def main():
    # ---- logging + crash handling first, so everything after this ----
    # ---- point is captured in the log file. --------------------------
    from services.logging_setup import setup_logging, install_excepthook
    setup_logging()

    app = QApplication(sys.argv)

    def _active_window():
        from qtpy.QtWidgets import QApplication as _Q
        return _Q.activeWindow()

    install_excepthook(parent_getter=_active_window)

    # ---- language + layout direction ----
    settings = QSettings("MembershipSystem", "app")
    lang = settings.value("language", "ar")
    from ui import i18n
    i18n.load(lang)
    if i18n.is_rtl():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    else:
        app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    # ---- single-instance lock ----
    # Prevents two copies of the app from opening the same SQLite file.
    # The lock is released automatically when the process exits.
    #
    # Kept alive for the rest of main() — the QLocalServer is released
    # when this object is garbage-collected. Since main() blocks on
    # app.exec() below, _instance_guard lives for the whole app.
    from services.instance_lock import SingleInstanceGuard
    _instance_guard = SingleInstanceGuard("AcademySystem-Membership")
    if not _instance_guard.acquire():
        from ui.message_box import info
        from ui.i18n import t
        info(
            None,
            t("app.already_running.title"),
            t("app.already_running.body"),
        )
        sys.exit(0)

    # ---- theme ----
    from ui.theme import theme
    theme().apply(app)

    # ---- first-run privacy consent ----
    # Shown once, on the very first launch. If declined, the app exits.
    from ui.dialogs.privacy_consent_dialog import ensure_privacy_consent
    if not ensure_privacy_consent():
        sys.exit(0)

    # ---- splash first, heavy work behind it ----
    from ui.splash import show_splash, finish_splash
    splash = show_splash()

    from db.database import init_db
    init_db()

    # ---- auto-backup + prune old ones (behind the splash) ----
    try:
        from services import backup_service
        backup_service.create_backup(label="auto")
        backup_service.prune_auto_backups(keep=14)
    except Exception as e:
        # A failed backup must never block startup.
        import logging
        logging.getLogger(__name__).exception("auto-backup on startup failed: %s", e)

    from ui.main_window import MainWindow

    finish_splash(splash)

    # ---- license ----
    from services import license_service
    lic_status = license_service.get_status()
    if not lic_status.valid:
        from ui.screens.license_screen import LicenseScreen
        lic_screen = LicenseScreen(lic_status)
        result = lic_screen.exec()
        if result != QDialog.DialogCode.Accepted:
            sys.exit(0)

    # ---- login ----
    from ui.screens.login_screen import LoginDialog
    login = LoginDialog()
    result = login.exec()
    if result != QDialog.DialogCode.Accepted:
        sys.exit(0)

    # ---- main window ----
    window = MainWindow()
    window.show()

    try:
        exit_code = app.exec()
    finally:
        # ---- auto-backup on close (best-effort) ----
        try:
            from services import backup_service
            backup_service.create_backup(label="auto")
            backup_service.prune_auto_backups(keep=14)
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(
                "auto-backup on close failed: %s", e
            )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()