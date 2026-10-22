"""
Migration 016 — v4 schema.

Combines:
- activities: add requires_belt, requires_weight, name (drop name_en/name_ar)
- players: add session_time
- player_measurements table
"""

VERSION = 16
DESCRIPTION = "v4 schema: activities requirements, session_time, measurements"

def up(conn):
    # Disable FKs so we can drop/rename activities while subs still reference it
    conn.execute("PRAGMA foreign_keys=OFF")

    try:
        # ============ ACTIVITIES ============
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activities_v4 (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                default_days TEXT NOT NULL,
                color TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                archived_at TEXT,
                requires_belt INTEGER NOT NULL DEFAULT 1,
                requires_weight INTEGER NOT NULL DEFAULT 1
            )
        """)

        cols = [r[1] for r in conn.execute("PRAGMA table_info(activities)").fetchall()]

        if "name" in cols:
            name_expr = "name"
            belt_expr = "COALESCE(requires_belt, 1)" if "requires_belt" in cols else "1"
            weight_expr = "COALESCE(requires_weight, 1)" if "requires_weight" in cols else "1"
        else:
            name_expr = "COALESCE(NULLIF(name_en, ''), name_ar, 'Unnamed')"
            belt_expr = "1"
            weight_expr = "1"

        conn.execute(f"""
            INSERT INTO activities_v4 (
                activity_id, name, default_days, color, active,
                created_at, archived_at, requires_belt, requires_weight
            )
            SELECT
                activity_id, {name_expr}, default_days, color, active,
                created_at, archived_at, {belt_expr}, {weight_expr}
            FROM activities
        """)

        conn.execute("DROP TABLE IF EXISTS activities_old")
        conn.execute("DROP TABLE activities")
        conn.execute("ALTER TABLE activities_v4 RENAME TO activities")

        # ============ PLAYERS: session_time ============
        player_cols = [r[1] for r in conn.execute("PRAGMA table_info(players)").fetchall()]
        if "session_time" not in player_cols:
            conn.execute("ALTER TABLE players ADD COLUMN session_time TEXT")

        # ============ PLAYER MEASUREMENTS ============
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_measurements (
                measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                recorded_at TEXT NOT NULL,
                weight_kg REAL,
                belt TEXT,
                notes TEXT,
                FOREIGN KEY (player_id) REFERENCES players (player_id) ON DELETE CASCADE
            )
        """)

    finally:
        conn.execute("PRAGMA foreign_keys=ON")