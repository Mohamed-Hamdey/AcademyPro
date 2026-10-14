"""
Application entry point.

Order:
  1. Init DB, load language, apply theme.
  2. License check — show LicenseScreen if unlicensed.
  3. Login — show LoginDialog.
  4. Main window.
"""

import sys
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import Qt, QSettings

from db.database import init_db
from ui import i18n
from ui.theme import theme


def main():
    init_db()

    settings = QSettings("MembershipSystem", "app")
    lang = settings.value("language", "ar")
    i18n.load(lang)

    app = QApplication(sys.argv)
    if i18n.is_rtl():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    else:
        app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    theme().apply(app)

    # ---- License check (before login) ----
    from services import license_service
    lic_status = license_service.get_status()
    if not lic_status.valid:
        from ui.screens.license_screen import LicenseScreen
        lic_screen = LicenseScreen(lic_status)
        result = lic_screen.exec()
        if result != QDialog.DialogCode.Accepted:
            print("[main] license not activated — exiting")
            sys.exit(0)
        print("[main] license accepted, proceeding to login")

    # ---- Login ----
    from ui.screens.login_screen import LoginDialog
    login = LoginDialog()
    result = login.exec()
    print(f"[main] login dialog returned: {result}")
    if result != QDialog.DialogCode.Accepted:
        print("[main] login cancelled or rejected — exiting")
        sys.exit(0)

    print("[main] opening main window")

    # ---- Main window ----
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    theme().apply(app)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()