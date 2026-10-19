"""
Migration 014 — Add activity_id to championships.

Context:
    Migration 013 recreated the `championships` table to unify the old
    `name_en` / `name_ar` columns into a single `name` column. This
    migration adds a nullable `activity_id` foreign-key-shaped column
    so championships can be filtered by activity.

Design notes:
    - SQLite silently ignores the `REFERENCES` clause on
      `ALTER TABLE ... ADD COLUMN` when the table already contains rows.
      We therefore declare the column as a plain INTEGER and rely on
      application-level validation (the form dialog requires an activity).
      If we ever turn on `PRAGMA foreign_keys = ON`, this column will need
      a full table recreation to get a real FK — same pattern as 013.
    - The column is NULLABLE so the ALTER succeeds on any pre-existing
      test rows. New saves are enforced as non-null by
      `ChampionshipFormDialog`. Legacy rows without an activity are
      "fixed on first edit" — non-destructive.
    - No `down()`: this project's migrations are up-only (matches 013).
"""

VERSION = 14
DESCRIPTION = "Link championships to activities"


def up(conn):
    conn.execute(
        "ALTER TABLE championships ADD COLUMN activity_id INTEGER"
    )