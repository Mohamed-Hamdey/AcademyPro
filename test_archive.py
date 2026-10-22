import sqlite3
from paths import AppPaths

db_path = AppPaths.database()
conn = sqlite3.connect(db_path)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

if "activities_old" in tables:
    conn.execute("DROP TABLE activities_old")
    conn.commit()
    print("✅ Cleaned up activities_old table.")
else:
    print("ℹ️ No activities_old table found — database is already clean.")

conn.close()