"""
Activities repository — SQL for the activities table.

Soft-delete via the `active` flag. Existing subscriptions still reference
the activity_id even after the activity is deactivated, so history is
preserved.
"""

import os
import sys
import json
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection


@dataclass
class Activity:
    activity_id: Optional[int]
    name: str
    default_days: list
    color: Optional[str] = None
    active: bool = True
    created_at: Optional[str] = None
    archived_at: Optional[str] = None
    requires_belt: bool = True          # <--- Added
    requires_weight: bool = True        # <--- Added

    @classmethod
    def from_row(cls, row) -> "Activity":
        keys = row.keys() if hasattr(row, "keys") else []
        try:
            days = json.loads(row["default_days"]) if row["default_days"] else []
        except (ValueError, TypeError):
            days = []
            
        return cls(
            activity_id=row["activity_id"],
            name=row["name"],
            default_days=days,
            color=row["color"],
            active=bool(row["active"]),
            created_at=row["created_at"],
            archived_at=row["archived_at"] if "archived_at" in keys else None,
            requires_belt=bool(row["requires_belt"]) if "requires_belt" in keys else True,
            requires_weight=bool(row["requires_weight"]) if "requires_weight" in keys else True,
        )

    def default_days_json(self) -> str:
        return json.dumps(self.default_days, ensure_ascii=False)


def create(name: str, default_days: list, color: str = None, requires_belt: bool = True, requires_weight: bool = True) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO activities (name, default_days, color, active, requires_belt, requires_weight)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (
                name,
                json.dumps(default_days, ensure_ascii=False),
                color,
                int(requires_belt),
                int(requires_weight),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update(activity_id: int, name: str, default_days: list, color: str = None, requires_belt: bool = True, requires_weight: bool = True) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE activities
            SET name = ?, default_days = ?, color = ?, requires_belt = ?, requires_weight = ?
            WHERE activity_id = ?
            """,
            (
                name,
                json.dumps(default_days, ensure_ascii=False),
                color,
                int(requires_belt),
                int(requires_weight),
                activity_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_by_id(activity_id: int) -> Optional[Activity]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM activities WHERE activity_id = ?", (activity_id,)
        ).fetchone()
        return Activity.from_row(row) if row else None
    finally:
        conn.close()


def list_all(include_inactive: bool = False) -> list[Activity]:
    conn = get_connection()
    try:
        if include_inactive:
            rows = conn.execute(
                "SELECT * FROM activities WHERE archived_at IS NULL ORDER BY active DESC, name"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM activities WHERE active = 1 AND archived_at IS NULL ORDER BY name"
            ).fetchall()
        return [Activity.from_row(r) for r in rows]
    finally:
        conn.close()


def set_active(activity_id: int, active: bool) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE activities SET active = ? WHERE activity_id = ?",
            (int(active), activity_id),
        )
        conn.commit()
    finally:
        conn.close()


def name_exists(name: str, exclude_id: Optional[int] = None) -> bool:
    """True if an active activity with this name already exists.
    Used to enforce unique names during creation/edit."""
    conn = get_connection()
    try:
        if exclude_id is None:
            row = conn.execute(
                "SELECT 1 FROM activities WHERE name = ? AND active = 1 LIMIT 1",
                (name,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM activities WHERE name = ? AND active = 1 AND activity_id != ? LIMIT 1",
                (name, exclude_id),
            ).fetchone()
        return row is not None
    finally:
        conn.close()


def count_active_subscriptions(activity_id: int) -> int:
    """
    How many subscriptions currently reference this activity (any status).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE activity_id = ?",
            (activity_id,),
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def count_active_subscriptions_by_status(activity_id: int) -> int:
    """
    How many subscriptions for this activity are currently 'active'.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM subscriptions "
            "WHERE activity_id = ? AND status = 'active'",
            (activity_id,),
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def delete(activity_id: int) -> None:
    """Permanently delete an activity from the DB. Only used if it has no references."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM activities WHERE activity_id = ?", (activity_id,))
        conn.commit()
    finally:
        conn.close()


def archive(activity_id: int) -> None:
    from datetime import datetime
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE activities SET archived_at = ? WHERE activity_id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), activity_id),
        )
        conn.commit()
    finally:
        conn.close()


def restore(activity_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE activities SET archived_at = NULL WHERE activity_id = ?",
            (activity_id,),
        )
        conn.commit()
    finally:
        conn.close()


def list_archived() -> list[Activity]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM activities WHERE archived_at IS NOT NULL ORDER BY archived_at DESC"
        ).fetchall()
        return [Activity.from_row(r) for r in rows]
    finally:
        conn.close()