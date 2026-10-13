import sys, os, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
db = os.path.join(os.environ["LOCALAPPDATA"], "AcademySystem", "academy.db")
conn = sqlite3.connect(db)
print("--- subscriptions columns ---")
for row in conn.execute("PRAGMA table_info(subscriptions)"):
    print(row)
conn.close()