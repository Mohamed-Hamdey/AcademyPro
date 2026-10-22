import sqlite3
from paths import AppPaths

conn = sqlite3.connect(AppPaths.database())

print("=== Tables ===")
for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    print(" ", r[0])

print("\n=== activities columns ===")
for r in conn.execute("PRAGMA table_info(activities)").fetchall():
    print(" ", r[1])

print("\n=== players has session_time? ===")
cols = [r[1] for r in conn.execute("PRAGMA table_info(players)").fetchall()]
print(" ", "session_time" in cols)

print("\n=== schema_version ===")
for r in conn.execute("SELECT version, description FROM schema_version ORDER BY version").fetchall():
    print(" ", r[0], r[1])

conn.close()