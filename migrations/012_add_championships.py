"""
Migration 012 — Championships feature.
"""

VERSION = 12
DESCRIPTION = "Add championships and registrations"


def up(conn):
    # --- Championships (The events) ---
    conn.execute(
        """
        CREATE TABLE championships (
            championship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_en         TEXT NOT NULL,
            name_ar         TEXT NOT NULL,
            event_date      TEXT NOT NULL,
            location        TEXT,
            entry_fee       REAL NOT NULL DEFAULT 0.0,
            notes           TEXT,
            archived_at     TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    # --- Championship Players (The assignments) ---
    conn.execute(
        """
        CREATE TABLE championship_players (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            championship_id     INTEGER NOT NULL,
            player_id           INTEGER NOT NULL,
            weight_kg           REAL,
            belt                TEXT,
            result              TEXT,  -- 'Gold', 'Silver', 'Bronze', 'Participant'
            notes               TEXT,
            registered_at       TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (championship_id) REFERENCES championships(championship_id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE,
            UNIQUE(championship_id, player_id)
        )
        """
    )

    conn.execute(
        "CREATE INDEX idx_champ_players_champ ON championship_players(championship_id)"
    )