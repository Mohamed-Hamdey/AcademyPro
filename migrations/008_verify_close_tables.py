"""
Migration 008 — verify close tables exist.

Migration 001 created `daily_close` and `monthly_close`. This migration
verifies their columns and adds any that are missing on very old DBs.

Idempotent.
"""

VERSION = 8
DESCRIPTION = "Verify daily_close and monthly_close tables"


def _cols(conn, table: str) -> set:
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def up(conn):
    # daily_close expected columns:
    #   close_date, revenue, expenses, new_players, total_checkins,
    #   closed_by, closed_at, notes
    dc = _cols(conn, "daily_close")
    if "daily_close" and not dc:
        conn.execute("""
            CREATE TABLE daily_close (
                close_date      TEXT PRIMARY KEY,
                revenue         REAL NOT NULL DEFAULT 0,
                expenses        REAL NOT NULL DEFAULT 0,
                new_players     INTEGER NOT NULL DEFAULT 0,
                total_checkins  INTEGER NOT NULL DEFAULT 0,
                closed_by       TEXT NOT NULL,
                closed_at       TEXT NOT NULL DEFAULT (datetime('now')),
                notes           TEXT
            )
        """)
    else:
        # Add missing columns (defensive; usually a no-op)
        for col, defn in [
            ("revenue",        "REAL NOT NULL DEFAULT 0"),
            ("expenses",       "REAL NOT NULL DEFAULT 0"),
            ("new_players",    "INTEGER NOT NULL DEFAULT 0"),
            ("total_checkins", "INTEGER NOT NULL DEFAULT 0"),
            ("closed_by",      "TEXT NOT NULL DEFAULT 'system'"),
            ("closed_at",      "TEXT"),
            ("notes",          "TEXT"),
        ]:
            if col not in dc:
                conn.execute(f"ALTER TABLE daily_close ADD COLUMN {col} {defn}")

    # monthly_close expected columns:
    #   close_month, revenue, expenses, closed_by, closed_at, notes
    mc = _cols(conn, "monthly_close")
    if "monthly_close" and not mc:
        conn.execute("""
            CREATE TABLE monthly_close (
                close_month     TEXT PRIMARY KEY,
                revenue         REAL NOT NULL DEFAULT 0,
                expenses        REAL NOT NULL DEFAULT 0,
                closed_by       TEXT NOT NULL,
                closed_at       TEXT NOT NULL DEFAULT (datetime('now')),
                notes           TEXT
            )
        """)
    else:
        for col, defn in [
            ("revenue",   "REAL NOT NULL DEFAULT 0"),
            ("expenses",  "REAL NOT NULL DEFAULT 0"),
            ("closed_by", "TEXT NOT NULL DEFAULT 'system'"),
            ("closed_at", "TEXT"),
            ("notes",     "TEXT"),
        ]:
            if col not in mc:
                conn.execute(f"ALTER TABLE monthly_close ADD COLUMN {col} {defn}")