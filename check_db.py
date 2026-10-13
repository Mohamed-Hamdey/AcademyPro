"""Quick diagnostic: list tables and check migration state."""
import os
import sqlite3

db_path = os.path.join(
    os.environ["LOCALAPPDATA"], "AcademySystem", "academy.db"
)
print(f"DB path: {db_path}")
print(f"Exists:  {os.path.exists(db_path)}")
print()

if not os.path.exists(db_path):
    print("No database file. Run `python main.py` once to trigger migrations.")
    raise SystemExit(0)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
)]
print("Tables:")
for t in tables:
    print(f"  - {t}")
print()

if "schema_version" in tables:
    rows = conn.execute("SELECT version, description, applied_at FROM schema_version").fetchall()
    print("schema_version:")
    for r in rows:
        print(f"  v{r['version']}: {r['description']}  (applied {r['applied_at']})")
else:
    print("schema_version table missing — migrations have not run.")
print()

if "activities" in tables:
    rows = conn.execute("SELECT activity_id, name_en, name_ar, default_days, active FROM activities").fetchall()
    print("activities:")
    for r in rows:
        print(f"  [{r['activity_id']}] {r['name_en']} / {r['name_ar']}  days={r['default_days']}  active={r['active']}")
else:
    print("activities table missing.")
print()

if "users" in tables:
    rows = conn.execute("SELECT user_id, username, role FROM users").fetchall()
    print("users:")
    for r in rows:
        print(f"  [{r['user_id']}] {r['username']}  role={r['role']}")
else:
    print("users table missing.")

conn.close()