"""
Migration 017 — Rebuild activities table to drop name_en/name_ar 
and enforce the new single 'name' column.
"""
VERSION = 17
DESCRIPTION = "Rebuild activities table to remove legacy name columns"

def up(conn):
    # 1. Temporarily disable Foreign Key enforcement for this transaction.
    # We MUST do this because we are dropping a table that other tables
    # (subscriptions, championships) are currently pointing to.
    conn.execute("PRAGMA foreign_keys=OFF")

    try:
        # 2. Rename the old table
        conn.execute("ALTER TABLE activities RENAME TO activities_old")

        # 3. Create the new, clean table
        conn.execute("""
            CREATE TABLE activities (
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

        # 4. Copy data from the old table to the new one
        conn.execute("""
            INSERT INTO activities (
                activity_id, name, default_days, color, active, 
                created_at, archived_at, requires_belt, requires_weight
            )
            SELECT 
                activity_id, 
                COALESCE(NULLIF(name, ''), name_en, name_ar, 'Unnamed') AS name,
                default_days, 
                color, 
                active, 
                created_at, 
                archived_at, 
                requires_belt, 
                requires_weight
            FROM activities_old
        """)

        # 5. Drop the old table
        conn.execute("DROP TABLE activities_old")

    finally:
        # 6. Re-enable Foreign Key enforcement
        conn.execute("PRAGMA foreign_keys=ON")