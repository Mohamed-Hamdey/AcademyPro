"""
Application entry point.
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

    # ---- Login ----
    from ui.screens.login_screen import LoginDialog
    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        # User closed the login dialog — exit cleanly.
        sys.exit(0)

    # ---- Main window ----
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    # Re-apply the theme once the window is built
    theme().apply(app)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()