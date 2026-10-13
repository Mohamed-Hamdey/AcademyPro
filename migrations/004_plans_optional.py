"""
Migration 004 — add allowed_days to subscriptions; plans become optional.

  * Adds `allowed_days TEXT` (JSON list) — the per-player training days
    for a subscription. Defaults to the activity's default_days when a
    subscription is created without an override.
  * No change to plan_type — it already allows NULL.
"""

import json

VERSION = 4
DESCRIPTION = "Add allowed_days to subscriptions; plans become presets"


def up(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(subscriptions)").fetchall()]

    if "allowed_days" not in cols:
        conn.execute("ALTER TABLE subscriptions ADD COLUMN allowed_days TEXT")

        # Backfill existing subscriptions: every current sub defaults to
        # Monday/Wednesday/Friday (the seeded Kung Fu activity's default days).
        # In this demo state there is likely nothing to backfill, but do it
        # just in case.
        default_days = json.dumps(["Monday", "Wednesday", "Friday"])
        conn.execute(
            "UPDATE subscriptions SET allowed_days = ? WHERE allowed_days IS NULL",
            (default_days,),
        )