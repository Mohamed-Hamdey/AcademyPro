"""
Migration 003 — indexes on audit_log.

The audit_log table exists since migration 001. Adding indexes for the
queries the audit screen runs: filter by user, by date, by action.
"""

VERSION = 3
DESCRIPTION = "Add indexes on audit_log"


def up(conn):
    existing = {r[1] for r in conn.execute(
        "SELECT type, name FROM sqlite_master WHERE type = 'index'"
    ).fetchall()}

    if "idx_audit_date" not in existing:
        conn.execute("CREATE INDEX idx_audit_date ON audit_log(created_at DESC)")

    if "idx_audit_user" not in existing:
        conn.execute("CREATE INDEX idx_audit_user ON audit_log(user_id)")

    if "idx_audit_action" not in existing:
        conn.execute("CREATE INDEX idx_audit_action ON audit_log(action)")

    if "idx_audit_target" not in existing:
        conn.execute("CREATE INDEX idx_audit_target ON audit_log(target_type, target_id)")