"""
Migration 005 — add missing columns to players.

Migration 001 created the players table without `qr_code_path` or
`status`, but the repository layer and UI expect both. This adds them.

  * qr_code_path — path to the player's QR PNG (nullable)
  * status       — 'active' or 'inactive', defaults to 'active'
"""

VERSION = 5
DESCRIPTION = "Add qr_code_path and status to players"


def up(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(players)").fetchall()]

    if "qr_code_path" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN qr_code_path TEXT")

    if "status" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
        )

    if "national_id" in cols:
        # Already there. Nothing to do.
        pass