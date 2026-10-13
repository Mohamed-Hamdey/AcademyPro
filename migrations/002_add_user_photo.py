"""
Migration 002 — add photo_path to users.

One new nullable TEXT column. SQLite supports ALTER TABLE ... ADD COLUMN
without needing a table rebuild, so this is a single statement.

Idempotent: if the column already exists (e.g. the migration was somehow
re-run), the ALTER fails with a specific error we catch and ignore.
"""

VERSION = 2
DESCRIPTION = "Add photo_path to users"


def up(conn):
    # Check whether the column already exists
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "photo_path" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN photo_path TEXT")