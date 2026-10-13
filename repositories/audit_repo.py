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