"""
Migration 013 — Unify championship names.
Replaces name_en and name_ar with a single 'name' column.
"""
VERSION = 13
DESCRIPTION = "Unify championship names"

def up(conn):
    # 1. Add the new column
    conn.execute("ALTER TABLE championships ADD COLUMN name TEXT")
    
    # 2. Migrate existing data (if any)
    conn.execute("UPDATE championships SET name = name_en || ' · ' || name_ar WHERE name IS NULL")
    
    # 3. Recreate the table to drop the old columns
    # SQLite requires recreating the table to drop columns cleanly.
    conn.execute("""
        CREATE TABLE championships_new (
            championship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            event_date      TEXT NOT NULL,
            location        TEXT,
            entry_fee       REAL NOT NULL DEFAULT 0.0,
            notes           TEXT,
            archived_at     TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        INSERT INTO championships_new (championship_id, name, event_date, location, entry_fee, notes, archived_at, created_at)
        SELECT championship_id, name, event_date, location, entry_fee, notes, archived_at, created_at FROM championships
    """)
    conn.execute("DROP TABLE championships")
    conn.execute("ALTER TABLE championships_new RENAME TO championships")