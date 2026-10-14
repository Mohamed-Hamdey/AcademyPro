"""
Attendance repository — all SQL touching the `attendance_log` table.
"""

import os
import sys
from datetime import date, datetime
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection
from models.attendance import AttendanceLog




def get_by_id(log_id: int) -> Optional[AttendanceLog]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM attendance_log WHERE log_id = ?", (log_id,)
        ).fetchone()
        return AttendanceLog.from_row(row) if row else None
    finally:
        conn.close()
def log(
    player_id: int,
    subscription_id: Optional[int],
    result: str,
    deny_reason: Optional[str],
    recorded_by: str,
    was_override: bool = False,
    override_note: Optional[str] = None,
    scan_datetime: Optional[str] = None,
) -> int:
    """
    Insert an attendance row.

    scan_datetime defaults to the current LOCAL time in ISO-ish format
    ("YYYY-MM-DD HH:MM:SS"). We pass it explicitly rather than relying on
    SQLite's `datetime('now')` default because SQLite uses UTC, which
    causes same-day checks to break around midnight for non-UTC timezones.
    """
    if scan_datetime is None:
        scan_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO attendance_log
                (player_id, subscription_id, scan_datetime, result, deny_reason,
                 was_override, override_note, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                player_id, subscription_id, scan_datetime, result, deny_reason,
                int(was_override), override_note, recorded_by,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
def get_for_player(player_id: int) -> list[AttendanceLog]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM attendance_log
            WHERE player_id = ?
            ORDER BY scan_datetime DESC
            """,
            (player_id,),
        ).fetchall()
        return [AttendanceLog.from_row(r) for r in rows]
    finally:
        conn.close()



def get_today_with_details(limit: int = 50) -> list[dict]:
    """
    Today's check-ins with everything the scan screen's Recent panel needs:

        log_id, player_id, player_name,
        scan_datetime, time_only,
        result, deny_reason, was_override, override_note,
        subscription_id, activity_id,
        activity_name_en, activity_name_ar,
        recorded_by

    Ordered newest first. Limited to today's calendar date in local time
    (substr(scan_datetime, 1, 10) = today).
    """
    from datetime import date as _date
    today_str = _date.today().isoformat()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT a.log_id,
                   a.player_id,
                   pl.full_name     AS player_name,
                   a.scan_datetime,
                   substr(a.scan_datetime, 12, 5) AS time_only,
                   a.result,
                   a.deny_reason,
                   a.was_override,
                   a.override_note,
                   a.subscription_id,
                   a.activity_id,
                   act.name_en      AS activity_name_en,
                   act.name_ar      AS activity_name_ar,
                   a.recorded_by
            FROM attendance_log a
            LEFT JOIN players    pl  ON pl.player_id    = a.player_id
            LEFT JOIN activities act ON act.activity_id = a.activity_id
            WHERE substr(a.scan_datetime, 1, 10) = ?
            ORDER BY a.scan_datetime DESC
            LIMIT ?
            """,
            (today_str, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
        
def get_by_date_with_details(day, limit: int = 200) -> list[dict]:
    """
    Same shape as get_today_with_details, but for an arbitrary date.

    `day` may be a datetime.date or an ISO string ("YYYY-MM-DD").
    Used by the full-log dialog's date picker.
    """
    from datetime import date as _date
    if isinstance(day, _date):
        day_str = day.isoformat()
    else:
        day_str = str(day)

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT a.log_id,
                   a.player_id,
                   pl.full_name     AS player_name,
                   a.scan_datetime,
                   substr(a.scan_datetime, 12, 5) AS time_only,
                   a.result,
                   a.deny_reason,
                   a.was_override,
                   a.override_note,
                   a.subscription_id,
                   a.activity_id,
                   act.name_en      AS activity_name_en,
                   act.name_ar      AS activity_name_ar,
                   a.recorded_by
            FROM attendance_log a
            LEFT JOIN players    pl  ON pl.player_id    = a.player_id
            LEFT JOIN activities act ON act.activity_id = a.activity_id
            WHERE substr(a.scan_datetime, 1, 10) = ?
            ORDER BY a.scan_datetime DESC
            LIMIT ?
            """,
            (day_str, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
def get_recent_with_names(limit: int = 5) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT a.scan_datetime, a.result, a.deny_reason, a.was_override, p.full_name
            FROM attendance_log a
            JOIN players p ON p.player_id = a.player_id
            ORDER BY a.scan_datetime DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def has_allowed_entry_on(player_id: int, on_date: date) -> bool:
    """
    True if this player has an 'allowed' attendance entry dated on_date.
    Denied entries do NOT count.
    """
    day_str = on_date.isoformat()
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT 1 FROM attendance_log
            WHERE player_id = ?
              AND result = 'allowed'
              AND substr(scan_datetime, 1, 10) = ?
            LIMIT 1
            """,
            (player_id, day_str),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def delete(log_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM attendance_log WHERE log_id = ?", (log_id,))
        conn.commit()
    finally:
        conn.close()