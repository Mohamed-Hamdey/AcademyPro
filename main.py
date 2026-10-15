"""
Application entry point.

Startup order: QApplication -> language/theme -> splash -> DB init ->
license check -> login -> MainWindow.
"""

import sys

from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import Qt, QSettings


def main():
    app = QApplication(sys.argv)

    # ---- language + layout direction ----
    settings = QSettings("MembershipSystem", "app")
    lang = settings.value("language", "ar")
    from ui import i18n
    i18n.load(lang)
    if i18n.is_rtl():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    else:
        app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    # ---- theme ----
    from ui.theme import theme
    theme().apply(app)

    # ---- splash first, heavy work behind it ----
    from ui.splash import show_splash, finish_splash
    splash = show_splash()

    from db.database import init_db
    init_db()

    # Pre-import MainWindow while the splash is up so the main window
    # appears instantly after login.
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

    sys.exit(app.exec())


if __name__ == "__main__":
    main()