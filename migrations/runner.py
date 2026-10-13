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
from typing import List, Tuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection


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

        for version, path, filename in _discover_migrations():
            if version <= current:
                continue

            module = _load_module(path)
            desc = getattr(module, "DESCRIPTION", filename)
            up = getattr(module, "up", None)
            if up is None:
                raise RuntimeError(
                    f"Migration {filename} doesn't define an up(conn) function"
                )

            print(f"[migrations] applying v{version}: {desc}")
            up(conn)
            conn.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (version, desc),
            )
            conn.commit()
            print(f"[migrations] v{version} applied")

        conn.commit()
    finally:
        conn.close()