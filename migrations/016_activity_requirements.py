"""
Migration 016 — Add belt/weight requirements to activities.
Also consolidates name_en/name_ar into a single 'name' column.
"""
VERSION = 16
DESCRIPTION = "Add belt/weight requirements and unify activity name"

def up(conn):
    # 1. Add the new requirement flags. Default to 1 (True) so existing
    # activities (Karate, Kung Fu) automatically require both.
    conn.execute("ALTER TABLE activities ADD COLUMN requires_belt INTEGER NOT NULL DEFAULT 1")
    conn.execute("ALTER TABLE activities ADD COLUMN requires_weight INTEGER NOT NULL DEFAULT 1")
    
    # 2. Add the new unified 'name' column.
    conn.execute("ALTER TABLE activities ADD COLUMN name TEXT")
    
    # 3. Backfill the 'name' column with the English name (falling back to Arabic).
    conn.execute("UPDATE activities SET name = COALESCE(name_en, name_ar, 'Unnamed Activity')")
    
    # Note: SQLite does not support DROP COLUMN in older versions, so we leave 
    # name_en and name_ar in the DB but the app will stop reading them.