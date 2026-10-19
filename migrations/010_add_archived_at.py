"""
Migration 010 — soft-delete support.

Adds an `archived_at` column to players and subscriptions. NULL means
"active" (shown in the app). A non-NULL timestamp means "archived"
(hidden from lists, visible only in the recycle bin).

Nothing reads these columns yet — that comes in sub-phase 3.3b. This
migration only adds the storage.
"""

VERSION = 10
DESCRIPTION = "Add archived_at to players and subscriptions"


def up(conn):
    # SQLite ALTER TABLE ADD COLUMN is safe here because:
    #   - The column is nullable (no default needed on existing rows)
    #   - We don't need a unique index or constraint
    # Existing rows automatically get NULL → treated as active.
    conn.execute(
        "ALTER TABLE players ADD COLUMN archived_at TEXT"
    )
    conn.execute(
        "ALTER TABLE subscriptions ADD COLUMN archived_at TEXT"
    )

    # Partial indexes — only index the archived rows, not the NULL ones.
    # This keeps the indexes small and fast even with thousands of
    # active players, since active rows (archived_at IS NULL) won't be
    # in the index at all.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_players_archived "
        "ON players(archived_at) WHERE archived_at IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_archived "
        "ON subscriptions(archived_at) WHERE archived_at IS NOT NULL"
    )