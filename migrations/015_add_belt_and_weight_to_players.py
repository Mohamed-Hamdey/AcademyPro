"""
Migration 015 — Add belt and weight_kg to players.
"""
VERSION = 15
DESCRIPTION = "Add belt and weight to players for championship pre-filling"

def up(conn):
    # Add belt column (defaults to 'white' if not set)
    conn.execute("ALTER TABLE players ADD COLUMN belt TEXT DEFAULT 'white'")
    
    # Add weight_kg column (nullable)
    conn.execute("ALTER TABLE players ADD COLUMN weight_kg REAL")