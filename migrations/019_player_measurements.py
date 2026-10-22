"""
Migration 019 — Player measurement history for weight and belt tracking.
"""
VERSION = 19
DESCRIPTION = "Add player_measurements table"

def up(conn):
    conn.execute("""
        CREATE TABLE player_measurements (
            measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            recorded_at TEXT NOT NULL,
            weight_kg REAL,
            belt TEXT,
            notes TEXT,
            FOREIGN KEY (player_id) REFERENCES players (player_id) ON DELETE CASCADE
        )
    """)
    # Add an index for quick lookup by player
    conn.execute("CREATE INDEX idx_measurements_player ON player_measurements(player_id)")