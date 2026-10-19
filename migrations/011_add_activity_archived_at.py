"""
Migration 011 — add archived_at to activities for recycle bin support.
"""
VERSION = 11
DESCRIPTION = "Add archived_at to activities"

def up(conn):
    conn.execute("ALTER TABLE activities ADD COLUMN archived_at TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_archived "
        "ON activities(archived_at) WHERE archived_at IS NOT NULL"
    )