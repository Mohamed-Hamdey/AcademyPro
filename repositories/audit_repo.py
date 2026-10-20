"""
Audit log repository — SQL for the audit_log table.
"""

import os
import sys
import json
from dataclasses import dataclass, field
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection


@dataclass
class AuditEntry:
    audit_id: Optional[int]
    user_id: Optional[int]
    username: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    details: Optional[str] = None      # JSON string
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "AuditEntry":
        return cls(
            audit_id=row["audit_id"],
            user_id=row["user_id"],
            username=row["username"],
            action=row["action"],
            target_type=row["target_type"],
            target_id=row["target_id"],
            details=row["details"],
            created_at=row["created_at"],
        )

    def details_dict(self) -> dict:
        """Parse the details JSON into a dict, or return {} if not set."""
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except (ValueError, TypeError):
            return {}


def write(
    user_id: Optional[int],
    username: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> int:
    """Insert an audit entry. `details` is serialized to JSON."""
    details_json = json.dumps(details, ensure_ascii=False) if details else None
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO audit_log
                (user_id, username, action, target_type, target_id, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, action, target_type, target_id, details_json),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def query(
    search: str = "",
    action: Optional[str] = None,
    username: Optional[str] = None,
    date_from: Optional[str] = None,   # ISO date YYYY-MM-DD
    date_to: Optional[str] = None,     # ISO date YYYY-MM-DD
    limit: int = 500,
) -> list[AuditEntry]:
    """
    Query the audit log with optional filters.

    - search: matches username or action substring (case-insensitive)
    - action: exact action code match
    - username: exact username match
    - date_from / date_to: inclusive date range on the created_at column
    """
    conn = get_connection()
    try:
        clauses = []
        params = []

        if search:
            like = f"%{search}%"
            clauses.append("(username LIKE ? OR action LIKE ? OR target_type LIKE ?)")
            params.extend([like, like, like])

        if action:
            clauses.append("action = ?")
            params.append(action)

        if username:
            clauses.append("username = ?")
            params.append(username)

        if date_from:
            clauses.append("substr(created_at, 1, 10) >= ?")
            params.append(date_from)

        if date_to:
            clauses.append("substr(created_at, 1, 10) <= ?")
            params.append(date_to)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)

        rows = conn.execute(
            f"""
            SELECT * FROM audit_log
            {where}
            ORDER BY audit_id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [AuditEntry.from_row(r) for r in rows]
    finally:
        conn.close()


def distinct_actions() -> list[str]:
    """All action codes that appear in the log, for the filter dropdown."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT action FROM audit_log ORDER BY action"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def distinct_usernames() -> list[str]:
    """All usernames that appear in the log, for the filter dropdown."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT username FROM audit_log ORDER BY username"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()
        
# ---------------------------------------------------------------------------
# Additions for the audit-screen rebuild (D1, 2026-04).
#
# These support:
#   - the footer ("Showing X of Y rows", "Oldest: DATE")
#   - the Clear button ("delete all")
#   - rolling retention ("delete rows older than N days")
#
# They are intentionally narrow single-purpose functions so the audit
# screen and the retention hook don't need to open their own connection.
# ---------------------------------------------------------------------------


def count() -> int:
    """Total number of rows in the audit log."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def count_matching(
    search: str = "",
    action: Optional[str] = None,
    username: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> int:
    """
    Row count for a filtered query. Same filter semantics as query().

    Used by the footer's "Showing X of Y rows" indicator so we can
    report the total a filtered view would return without pulling
    every row into Python.
    """
    conn = get_connection()
    try:
        clauses = []
        params = []

        if search:
            like = f"%{search}%"
            clauses.append(
                "(username LIKE ? OR action LIKE ? OR target_type LIKE ?)"
            )
            params.extend([like, like, like])

        if action:
            clauses.append("action = ?")
            params.append(action)

        if username:
            clauses.append("username = ?")
            params.append(username)

        if date_from:
            clauses.append("substr(created_at, 1, 10) >= ?")
            params.append(date_from)

        if date_to:
            clauses.append("substr(created_at, 1, 10) <= ?")
            params.append(date_to)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        row = conn.execute(
            f"SELECT COUNT(*) FROM audit_log {where}",
            params,
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def oldest_created_at() -> Optional[str]:
    """MIN(created_at) — ISO string of the oldest row, or None if empty."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT MIN(created_at) FROM audit_log"
        ).fetchone()
        return row[0] if row and row[0] is not None else None
    finally:
        conn.close()


def delete_all() -> int:
    """
    Wipe the entire audit log. Returns the number of rows deleted.

    Callers MUST be aware this is destructive and irreversible. The
    audit service wraps this with a self-audit (audit.clear) so the
    clear action leaves a single trace row behind.
    """
    conn = get_connection()
    try:
        # Get count first so we can report how many rows were removed.
        row = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
        total = int(row[0]) if row else 0
        conn.execute("DELETE FROM audit_log")
        conn.commit()
        return total
    finally:
        conn.close()


def delete_before(iso_datetime: str) -> int:
    """
    Delete every row whose created_at is strictly less than iso_datetime
    ('YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD'). Returns the number of rows
    deleted.

    Called by audit_service.purge_older_than() — rolling retention.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE created_at < ?",
            (iso_datetime,),
        ).fetchone()
        total = int(row[0]) if row else 0
        if total:
            conn.execute(
                "DELETE FROM audit_log WHERE created_at < ?",
                (iso_datetime,),
            )
            conn.commit()
        return total
    finally:
        conn.close()