"""
Dashboard service — aggregation queries for the daily view.

Groups everything the daily dashboard needs into one service so the
screen doesn't scatter SQL across multiple repos.
"""

import os
import sys
from datetime import date, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection


# ---------------------------------------------------------------------------
# Daily aggregations
# ---------------------------------------------------------------------------

def day_summary(d: date) -> dict:
    """
    One dict with everything the daily dashboard shows.

    Keys:
        date                  — the day
        revenue               — sum of payments.amount for that day
        revenue_count         — number of payments
        expenses              — sum of expenses.amount (0 until 4.3)
        expenses_count        — number of expenses
        net                   — revenue - expenses
        attendance_total      — count of allowed attendance on that day
        attendance_by_activity— list of dicts {activity_id, name_en, name_ar, count}
        new_players           — count of players created that day
        payments              — list of payments with player names
        new_player_list       — list of players created that day
        low_session_players   — players with an active sub that has <= 2 sessions left
        expiring_soon         — active subs expiring within the next 7 days
    """
    iso = d.isoformat()

    summary = {
        "date": iso,
        "revenue": 0.0,
        "revenue_count": 0,
        "expenses": 0.0,
        "expenses_count": 0,
        "net": 0.0,
        "attendance_total": 0,
        "attendance_by_activity": [],
        "new_players": 0,
        "payments": [],
        "new_player_list": [],
        "low_session_players": [],
        "expiring_soon": [],
    }

    # --- Revenue ---
    summary.update(_revenue_for_day(d))

    # --- Expenses (safe until the expenses table is populated) ---
    summary.update(_expenses_for_day(d))

    summary["net"] = summary["revenue"] - summary["expenses"]

    # --- Attendance ---
    summary.update(_attendance_for_day(d))

    # --- New players ---
    summary.update(_new_players_for_day(d))

    # --- Payments list ---
    summary["payments"] = _payments_for_day(d)

    # --- Alerts ---
    summary["low_session_players"] = _low_session_players()
    summary["expiring_soon"] = _expiring_soon()

    return summary


# ---------------------------------------------------------------------------

def _revenue_for_day(d: date) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total,
                   COUNT(*) AS cnt
            FROM payments
            WHERE payment_date = ?
            """,
            (d.isoformat(),),
        ).fetchone()
        return {
            "revenue": float(row["total"]) if row else 0.0,
            "revenue_count": int(row["cnt"]) if row else 0,
        }
    finally:
        conn.close()


def _expenses_for_day(d: date) -> dict:
    conn = get_connection()
    try:
        # expenses table exists but may have no rows
        row = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total,
                   COUNT(*) AS cnt
            FROM expenses
            WHERE expense_date = ?
            """,
            (d.isoformat(),),
        ).fetchone()
        return {
            "expenses": float(row["total"]) if row else 0.0,
            "expenses_count": int(row["cnt"]) if row else 0,
        }
    except Exception:
        return {"expenses": 0.0, "expenses_count": 0}
    finally:
        conn.close()


def _attendance_for_day(d: date) -> dict:
    iso = d.isoformat()
    conn = get_connection()
    try:
        # Total allowed
        row = conn.execute(
            """
            SELECT COUNT(*) FROM attendance_log
            WHERE substr(scan_datetime, 1, 10) = ?
              AND result = 'allowed'
            """,
            (iso,),
        ).fetchone()
        total = int(row[0]) if row else 0

        # By activity
        rows = conn.execute(
            """
            SELECT a.activity_id,
                   COALESCE(act.name_en, '?') AS name_en,
                   COALESCE(act.name_ar, '?') AS name_ar,
                   COUNT(*) AS cnt
            FROM attendance_log a
            LEFT JOIN activities act ON act.activity_id = a.activity_id
            WHERE substr(a.scan_datetime, 1, 10) = ?
              AND a.result = 'allowed'
            GROUP BY a.activity_id
            ORDER BY cnt DESC
            """,
            (iso,),
        ).fetchall()
        by_activity = [dict(r) for r in rows]
    finally:
        conn.close()
    return {"attendance_total": total, "attendance_by_activity": by_activity}


def _new_players_for_day(d: date) -> dict:
    iso = d.isoformat()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT player_id, full_name, phone, created_at
            FROM players
            WHERE substr(created_at, 1, 10) = ?
            ORDER BY created_at DESC
            """,
            (iso,),
        ).fetchall()
        players = [dict(r) for r in rows]
    finally:
        conn.close()
    return {"new_players": len(players), "new_player_list": players}


def _payments_for_day(d: date) -> list[dict]:
    iso = d.isoformat()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT p.payment_id, p.amount, p.currency, p.method,
                   p.payment_date, p.notes, p.recorded_by,
                   pl.full_name AS player_name,
                   s.subscription_id, s.activity_id,
                   act.name_en AS activity_name_en,
                   act.name_ar AS activity_name_ar
            FROM payments p
            JOIN players pl ON pl.player_id = p.player_id
            LEFT JOIN subscriptions s ON s.subscription_id = p.subscription_id
            LEFT JOIN activities act ON act.activity_id = s.activity_id
            WHERE p.payment_date = ?
            ORDER BY p.payment_id DESC
            """,
            (iso,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _low_session_players(threshold: int = 2) -> list[dict]:
    """
    Active subs with <= threshold sessions remaining. Sorted ascending
    so the smallest count comes first.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT s.subscription_id, s.sessions_remaining, s.sessions_total,
                   s.activity_id,
                   pl.player_id, pl.full_name,
                   act.name_en AS activity_name_en,
                   act.name_ar AS activity_name_ar
            FROM subscriptions s
            JOIN players pl ON pl.player_id = s.player_id
            LEFT JOIN activities act ON act.activity_id = s.activity_id
            WHERE s.status = 'active'
              AND s.sessions_remaining <= ?
              AND s.expiry_date >= date('now')
            ORDER BY s.sessions_remaining ASC, pl.full_name
            """,
            (threshold,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Monthly aggregations
# ---------------------------------------------------------------------------

def month_summary(year: int, month: int) -> dict:
    """
    Everything the monthly dashboard needs.

    Keys:
        year, month
        revenue           — sum of payments in the month
        revenue_count
        expenses          — sum of expenses in the month
        expenses_count
        net               — revenue - expenses
        attendance_total  — count of allowed scans in the month
        revenue_by_activity — list of {activity_id, name, total, count}
        revenue_by_method   — list of {method, total, count}
        expenses_by_category — list of {category, total, count}
        new_players       — count of players created in the month
        new_player_list   — list of dicts
    """
    import calendar
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    iso_first = first.isoformat()
    iso_last = last.isoformat()

    conn = get_connection()
    try:
        # Revenue
        row = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt
            FROM payments
            WHERE payment_date >= ? AND payment_date <= ?
            """,
            (iso_first, iso_last),
        ).fetchone()
        revenue = float(row["total"]) if row else 0.0
        revenue_count = int(row["cnt"]) if row else 0

        # Expenses
        try:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt
                FROM expenses
                WHERE expense_date >= ? AND expense_date <= ?
                """,
                (iso_first, iso_last),
            ).fetchone()
            expenses = float(row["total"]) if row else 0.0
            expenses_count = int(row["cnt"]) if row else 0
        except Exception:
            expenses = 0.0
            expenses_count = 0

        # Attendance
        row = conn.execute(
            """
            SELECT COUNT(*) FROM attendance_log
            WHERE substr(scan_datetime, 1, 10) >= ?
              AND substr(scan_datetime, 1, 10) <= ?
              AND result = 'allowed'
            """,
            (iso_first, iso_last),
        ).fetchone()
        attendance_total = int(row[0]) if row else 0

        # Revenue by activity
        rows = conn.execute(
            """
            SELECT s.activity_id,
                   COALESCE(act.name_en, '?') AS name_en,
                   COALESCE(act.name_ar, '?') AS name_ar,
                   COALESCE(SUM(p.amount), 0) AS total,
                   COUNT(p.payment_id) AS count
            FROM payments p
            LEFT JOIN subscriptions s ON s.subscription_id = p.subscription_id
            LEFT JOIN activities act ON act.activity_id = s.activity_id
            WHERE p.payment_date >= ? AND p.payment_date <= ?
              AND s.activity_id IS NOT NULL
            GROUP BY s.activity_id
            ORDER BY total DESC
            """,
            (iso_first, iso_last),
        ).fetchall()
        revenue_by_activity = [dict(r) for r in rows]

        # Revenue by method
        rows = conn.execute(
            """
            SELECT method, COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count
            FROM payments
            WHERE payment_date >= ? AND payment_date <= ?
            GROUP BY method
            ORDER BY total DESC
            """,
            (iso_first, iso_last),
        ).fetchall()
        revenue_by_method = [dict(r) for r in rows]

        # Expenses by category
        try:
            rows = conn.execute(
                """
                SELECT category, COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count
                FROM expenses
                WHERE expense_date >= ? AND expense_date <= ?
                GROUP BY category
                ORDER BY total DESC
                """,
                (iso_first, iso_last),
            ).fetchall()
            expenses_by_category = [dict(r) for r in rows]
        except Exception:
            expenses_by_category = []

        # New players
        rows = conn.execute(
            """
            SELECT player_id, full_name, phone, created_at
            FROM players
            WHERE substr(created_at, 1, 10) >= ?
              AND substr(created_at, 1, 10) <= ?
            ORDER BY created_at DESC
            """,
            (iso_first, iso_last),
        ).fetchall()
        new_player_list = [dict(r) for r in rows]
    finally:
        conn.close()

    return {
        "year": year, "month": month,
        "revenue": revenue, "revenue_count": revenue_count,
        "expenses": expenses, "expenses_count": expenses_count,
        "net": revenue - expenses,
        "attendance_total": attendance_total,
        "revenue_by_activity": revenue_by_activity,
        "revenue_by_method": revenue_by_method,
        "expenses_by_category": expenses_by_category,
        "new_players": len(new_player_list),
        "new_player_list": new_player_list,
    }
def _expiring_soon(days: int = 7) -> list[dict]:
    """Active subs whose expiry falls within the next N days (inclusive)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT s.subscription_id, s.expiry_date, s.sessions_remaining,
                   s.sessions_total, s.activity_id,
                   pl.player_id, pl.full_name,
                   act.name_en AS activity_name_en,
                   act.name_ar AS activity_name_ar
            FROM subscriptions s
            JOIN players pl ON pl.player_id = s.player_id
            LEFT JOIN activities act ON act.activity_id = s.activity_id
            WHERE s.status = 'active'
              AND s.expiry_date >= date('now')
              AND s.expiry_date <= date('now', '+' || ? || ' day')
            ORDER BY s.expiry_date ASC, pl.full_name
            """,
            (days,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()