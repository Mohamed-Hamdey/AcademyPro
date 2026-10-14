"""
Close service — snapshots the numbers for a day or a month.

Design: a close is a frozen snapshot of what was known at the moment of
closing. It does NOT lock the books. Late payments can still be recorded
with their real (old) date; the snapshot stays as the historical record.

Closing twice: allowed but overwrites. The dashboard shows the latest
snapshot. If you need to keep two, snapshot one to PDF before re-closing.
"""

import os
import sys
from datetime import date
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection
from services import dashboard_service
from app_state import app as app_state


@dataclass
class DayClose:
    close_date: str
    revenue: float
    expenses: float
    new_players: int
    total_checkins: int
    closed_by: str
    closed_at: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class MonthClose:
    close_month: str         # "YYYY-MM"
    revenue: float
    expenses: float
    closed_by: str
    closed_at: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Day close
# ---------------------------------------------------------------------------

def close_day(d: date, notes: str = None) -> DayClose:
    """
    Compute today's (or the given day's) summary and save a snapshot.
    Overwrites any previous close for the same date.
    """
    summary = dashboard_service.day_summary(d)
    closed_by = app_state.recorded_by() or "system"

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO daily_close
                (close_date, revenue, expenses, new_players, total_checkins,
                 closed_by, closed_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
            ON CONFLICT(close_date) DO UPDATE SET
                revenue = excluded.revenue,
                expenses = excluded.expenses,
                new_players = excluded.new_players,
                total_checkins = excluded.total_checkins,
                closed_by = excluded.closed_by,
                closed_at = excluded.closed_at,
                notes = excluded.notes
            """,
            (
                d.isoformat(),
                summary["revenue"],
                summary["expenses"],
                summary["new_players"],
                summary["attendance_total"],
                closed_by,
                notes,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return get_day_close(d)


def get_day_close(d: date) -> Optional[DayClose]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM daily_close WHERE close_date = ?",
            (d.isoformat(),),
        ).fetchone()
        if row is None:
            return None
        return DayClose(
            close_date=row["close_date"],
            revenue=row["revenue"],
            expenses=row["expenses"],
            new_players=row["new_players"],
            total_checkins=row["total_checkins"],
            closed_by=row["closed_by"],
            closed_at=row["closed_at"],
            notes=row["notes"],
        )
    finally:
        conn.close()


def is_day_closed(d: date) -> bool:
    return get_day_close(d) is not None


def reopen_day(d: date) -> None:
    """Delete the snapshot for a day so it can be re-closed with new numbers."""
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM daily_close WHERE close_date = ?",
            (d.isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Month close
# ---------------------------------------------------------------------------

def _month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def close_month(year: int, month: int, notes: str = None) -> MonthClose:
    summary = dashboard_service.month_summary(year, month)
    closed_by = app_state.recorded_by() or "system"
    key = _month_key(year, month)

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO monthly_close
                (close_month, revenue, expenses, closed_by, closed_at, notes)
            VALUES (?, ?, ?, ?, datetime('now'), ?)
            ON CONFLICT(close_month) DO UPDATE SET
                revenue = excluded.revenue,
                expenses = excluded.expenses,
                closed_by = excluded.closed_by,
                closed_at = excluded.closed_at,
                notes = excluded.notes
            """,
            (
                key,
                summary["revenue"],
                summary["expenses"],
                closed_by,
                notes,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return get_month_close(year, month)


def get_month_close(year: int, month: int) -> Optional[MonthClose]:
    key = _month_key(year, month)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM monthly_close WHERE close_month = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return MonthClose(
            close_month=row["close_month"],
            revenue=row["revenue"],
            expenses=row["expenses"],
            closed_by=row["closed_by"],
            closed_at=row["closed_at"],
            notes=row["notes"],
        )
    finally:
        conn.close()


def is_month_closed(year: int, month: int) -> bool:
    return get_month_close(year, month) is not None


def reopen_month(year: int, month: int) -> None:
    key = _month_key(year, month)
    conn = get_connection()
    try:
        conn.execute("DELETE FROM monthly_close WHERE close_month = ?", (key,))
        conn.commit()
    finally:
        conn.close()