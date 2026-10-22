"""
Migration 018 — Add session_time to players.
"""
VERSION = 18
DESCRIPTION = "Add preferred session time to players"

def up(conn):
    conn.execute("ALTER TABLE players ADD COLUMN session_time TEXT")