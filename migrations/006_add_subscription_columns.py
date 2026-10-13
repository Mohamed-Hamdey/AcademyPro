"""
Migration 006 — add missing columns to subscriptions.

Migration 001 created the subscriptions table without these three
columns, but the code writes to all of them:

  * plan_type       — legacy preset key ('4'/'8'/'12') or NULL
  * payment_amount  — the payment amount in EGP
  * payment_date    — ISO date the payment was recorded
"""

VERSION = 6
DESCRIPTION = "Add plan_type, payment_amount, payment_date to subscriptions"


def up(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(subscriptions)").fetchall()]

    if "plan_type" not in cols:
        conn.execute("ALTER TABLE subscriptions ADD COLUMN plan_type TEXT")

    if "payment_amount" not in cols:
        conn.execute("ALTER TABLE subscriptions ADD COLUMN payment_amount REAL")

    if "payment_date" not in cols:
        conn.execute("ALTER TABLE subscriptions ADD COLUMN payment_date TEXT")