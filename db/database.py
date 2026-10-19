"""
Database connection helper.

Local-only storage: a single SQLite file, in the user's LocalAppData
folder on Windows. The schema (.sql) ships inside the app bundle and is
read from there. The database itself is writable user data.
"""

import sqlite3
import os
import sys
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from paths import AppPaths, user_data_root

DB_PATH = AppPaths.database()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Retry for up to 5s when the DB is locked (e.g. backup running,
    # antivirus scanning, another process touching the file).
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

def init_db() -> None:
    """
    Initialize the database.

    1. If a DB already exists, verify its integrity.
       If the check fails, show a themed dialog offering to restore from
       the latest backup or quit.
    2. Run pending migrations (with a pre-migration snapshot taken
       automatically — see migrations/runner.py).
    Safe to call every time the app starts.
    """
    import logging
    log = logging.getLogger(__name__)

    # --- Integrity check (only if the DB exists) ---
    if os.path.exists(DB_PATH):
        from services import db_safety
        ok, reason = db_safety.check_integrity(DB_PATH)
        if not ok:
            log.error("Database failed integrity check: %s", reason)
            if not _handle_integrity_failure(reason):
                # User chose not to recover — abort startup.
                sys.exit(1)

    # --- Migrations ---
    try:
        from migrations.runner import run_migrations
        run_migrations()
    except Exception as e:
        log.exception("Migrations failed: %s", e)
        _handle_migration_failure(e)
        sys.exit(1)


def _handle_integrity_failure(reason: str) -> bool:
    """
    Show a themed dialog when the DB is corrupted.
    Returns True if the user chose to attempt a restore-from-backup,
    False if they chose to quit.

    A restore attempt always replaces academy.db with the newest backup
    that passes an integrity check. If no valid backup exists, the user
    is told and the app quits.
    """
    # Qt imports are lazy: init_db may be called from scripts (e.g.
    # seed_test_data.py) that don't want to start a QApplication.
    try:
        from qtpy.QtWidgets import QApplication
        if QApplication.instance() is None:
            # No GUI — just log and refuse to proceed.
            logging.getLogger(__name__).error(
                "Integrity check failed: %s", reason
            )
            return False
    except Exception:
        return False

    from ui.message_box import ask, warn, error
    from ui.i18n import t

    proceed = ask(
        None,
        t("db.integrity.fail_title"),
        t("db.integrity.fail_body", reason=reason),
    )
    if not proceed:
        return False

    # Try restoring the newest backup that passes an integrity check.
    from services import backup_service, db_safety
    for b in backup_service.list_backups():
        if db_safety.check_integrity(b["path"])[0]:
            ok = backup_service.restore_backup(b["path"])
            if ok:
                return True
            error(
                None,
                t("db.integrity.restore_failed_title"),
                t("db.integrity.restore_failed_body"),
            )
            return False

    warn(
        None,
        t("db.integrity.no_backup_title"),
        t("db.integrity.no_backup_body"),
    )
    return False


def _handle_migration_failure(exc: Exception) -> None:
    """Show a themed dialog if a migration failed and a snapshot was restored."""
    try:
        from qtpy.QtWidgets import QApplication
        if QApplication.instance() is None:

            logging.getLogger(__name__).exception(
                "Migration failed", exc_info=exc
            )
            return
    except Exception:
        return

    from ui.message_box import error
    from ui.i18n import t
    error(
        None,
        t("db.migration.fail_title"),
        t("db.migration.fail_body"),
    )

if __name__ == "__main__":
    init_db()
    print(f"Database ready at: {DB_PATH}")
    print(f"User data root:    {user_data_root()}")