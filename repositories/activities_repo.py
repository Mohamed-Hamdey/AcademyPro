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
        
        
def get_activity_kpis(activity_id: int, date_from: str, date_to: str) -> dict:
    """
    Returns a dictionary of raw numbers for the KPI strip.
    """
    conn = get_connection()
    try:
        # 1. Active Players (Current Snapshot, ignores date range)
        active_row = conn.execute(
            "SELECT COUNT(DISTINCT player_id) FROM subscriptions "
            "WHERE activity_id = ? AND status = 'active' AND archived_at IS NULL",
            (activity_id,)
        ).fetchone()
        
        # 2. Revenue in Period
        rev_row = conn.execute(
            """
            SELECT COALESCE(SUM(p.amount), 0) 
            FROM payments p
            JOIN subscriptions s ON s.subscription_id = p.subscription_id
            WHERE s.activity_id = ? AND p.payment_date >= ? AND p.payment_date <= ?
            """,
            (activity_id, date_from, date_to)
        ).fetchone()

        # 3. Attendance in Period
        att_row = conn.execute(
            """
            SELECT COUNT(*) 
            FROM attendance_log a
            JOIN subscriptions s ON s.subscription_id = a.subscription_id
            WHERE s.activity_id = ? AND a.result = 'allowed'
              AND substr(a.scan_datetime, 1, 10) >= ? AND substr(a.scan_datetime, 1, 10) <= ?
            """,
            (activity_id, date_from, date_to)
        ).fetchone()

        # 4. Expiring in 7 Days (Current Snapshot)
        exp_row = conn.execute(
            """
            SELECT COUNT(*) FROM subscriptions
            WHERE activity_id = ? AND status = 'active' AND archived_at IS NULL
              AND expiry_date >= date('now') AND expiry_date <= date('now', '+7 days')
            """,
            (activity_id,)
        ).fetchone()

        # 5. Low Sessions (Current Snapshot)
        low_row = conn.execute(
            """
            SELECT COUNT(*) FROM subscriptions
            WHERE activity_id = ? AND status = 'active' AND archived_at IS NULL
              AND sessions_remaining <= 1
            """,
            (activity_id,)
        ).fetchone()

        return {
            "active_players": active_row[0] if active_row else 0,
            "revenue": float(rev_row[0]) if rev_row else 0.0,
            "attendance": int(att_row[0]) if att_row else 0,
            "expiring_soon": int(exp_row[0]) if exp_row else 0,
            "low_sessions": int(low_row[0]) if low_row else 0,
        }
    finally:
        conn.close()


def get_activity_charts(activity_id: int, months: int = 6, weeks: int = 8) -> dict:
    """
    Returns data for the two charts (Revenue by Month, Attendance by Week).
    """
    import datetime
    import calendar
    conn = get_connection()
    today = datetime.date.today()
    
    revenue_data = []
    attendance_data = []
    
    try:
        # --- Revenue by Month (Last N months) ---
        for i in range(months - 1, -1, -1):
            total_months = today.year * 12 + today.month - 1 - i
            y = total_months // 12
            m = (total_months % 12) + 1
            first_day = datetime.date(y, m, 1).isoformat()
            last_day = datetime.date(y, m, calendar.monthrange(y, m)[1]).isoformat()
            
            row = conn.execute(
                """
                SELECT COALESCE(SUM(p.amount), 0) 
                FROM payments p
                JOIN subscriptions s ON s.subscription_id = p.subscription_id
                WHERE s.activity_id = ? AND p.payment_date >= ? AND p.payment_date <= ?
                """,
                (activity_id, first_day, last_day)
            ).fetchone()
            
            revenue_data.append({
                "month_label": datetime.date(y, m, 1).strftime("%b %Y"),
                "total": float(row[0]) if row else 0.0,
            })

        # --- Attendance by Week (Last N weeks) ---
        start_of_this_week = today - datetime.timedelta(days=today.weekday())
        for i in range(weeks - 1, -1, -1):
            week_start = start_of_this_week - datetime.timedelta(weeks=i)
            week_end = week_start + datetime.timedelta(days=6)
            
            row = conn.execute(
                """
                SELECT COUNT(*) 
                FROM attendance_log a
                JOIN subscriptions s ON s.subscription_id = a.subscription_id
                WHERE s.activity_id = ? AND a.result = 'allowed'
                  AND substr(a.scan_datetime, 1, 10) >= ? AND substr(a.scan_datetime, 1, 10) <= ?
                """,
                (activity_id, week_start.isoformat(), week_end.isoformat())
            ).fetchone()
            
            attendance_data.append({
                "week_label": week_start.strftime("%b %d"),
                "count": int(row[0]) if row else 0,
            })
            
    finally:
        conn.close()
        
    return {
        "revenue": revenue_data,
        "attendance": attendance_data
    }