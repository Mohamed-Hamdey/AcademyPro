"""
Migration runner.

On every app startup, look at the `schema_version` table and apply any
migrations that haven't run yet, in order.

Migration files live in this folder, named `NNN_description.py` (e.g.
`001_v2_initial.py`). Each must expose:

    VERSION = 1
    DESCRIPTION = "Initial v2 schema"
    def up(conn): ...      # apply the migration

`conn` is a sqlite3.Connection. Because Python's sqlite3 `executescript()`
auto-commits, migrations are NOT run inside a single transaction — they
must be written to be safe against partial completion (use
IF NOT EXISTS / IF EXISTS liberally).
"""

import os
import sys
import importlib.util
import logging
from typing import List, Tuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection


log = logging.getLogger(__name__)


MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))


def _ensure_version_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def _current_version(conn) -> int:
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] if row and row[0] is not None else 0


def _discover_migrations() -> List[Tuple[int, str, str]]:
    migrations = []
    # Defensive: if the migrations folder wasn't bundled (frozen build
    # with a stale spec), don't crash — just log and return empty.
    if not os.path.isdir(MIGRATIONS_DIR):
        import logging
        logging.getLogger(__name__).warning(
            "Migrations folder not found at %s — skipping migrations",
            MIGRATIONS_DIR,
        )
        return migrations

    for name in sorted(os.listdir(MIGRATIONS_DIR)):
        if not name.endswith(".py"):
            continue
        if name.startswith("_"):
            continue
        if not name[0].isdigit():
            continue
        try:
            version = int(name.split("_", 1)[0])
        except ValueError:
            continue
        path = os.path.join(MIGRATIONS_DIR, name)
        migrations.append((version, path, name))
    migrations.sort(key=lambda x: x[0])
    return migrations


def _load_module(path: str):
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_migrations() -> None:
    """Apply any pending migrations. Idempotent — safe to call on every launch."""
    conn = get_connection()
    try:
        _ensure_version_table(conn)
        current = _current_version(conn)

        # Collect the migrations that actually need to run.
        pending = []
        for version, path, filename in _discover_migrations():
            if version <= current:
                continue
            pending.append((version, path, filename))

        if not pending:
            conn.commit()
            return

        # --- Pre-migration backup of the whole DB (only when needed) ---
        # We snapshot once, before the first pending migration. If any
        # migration in the batch fails, we restore that single snapshot.
        from services import db_safety
        first_version = pending[0][0]
        snapshot_path = db_safety.take_pre_migration_snapshot(first_version)

        try:
            for version, path, filename in pending:
                module = _load_module(path)
                desc = getattr(module, "DESCRIPTION", filename)
                up = getattr(module, "up", None)
                if up is None:
                    raise RuntimeError(
                        f"Migration {filename} doesn't define an up(conn) function"
                    )

                log.info("Applying migration v%d: %s", version, desc)
                up(conn)
                conn.execute(
                    "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                    (version, desc),
                )
                conn.commit()
                log.info("Migration v%d applied", version)

        except Exception:
            # A migration failed. Close the connection, restore the
            # snapshot, and re-raise so the caller can show a dialog.
            log.exception("Migration failed — restoring pre-migration snapshot")
            try:
                conn.close()
            except Exception:
                pass

            if snapshot_path is not None:
                db_safety.restore_pre_migration_snapshot(first_version)

            raise

        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass