"""
Activity service — business logic for activities.

Wraps the repository with validation, localized name lookups, and a
"safe delete" that checks for references before deactivating.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from repositories import activities_repo
from repositories.activities_repo import Activity
from ui import i18n


def list_active() -> list[Activity]:
    return activities_repo.list_all(include_inactive=False)


def list_all() -> list[Activity]:
    return activities_repo.list_all(include_inactive=True)


def get(activity_id: int) -> Activity | None:
    return activities_repo.get_by_id(activity_id)


def get_localized_name(activity) -> str:
    if hasattr(activity, "name"):
        return activity.name
    return "—"


def create(name: str, default_days: list, color: str = None, requires_belt: bool = True, requires_weight: bool = True) -> int:
    """Create a new activity."""
    # (Keep whatever validation you have here, e.g., name_exists)
    
    # Pass the new parameters to the repo
    return activities_repo.create(
        name=name, 
        default_days=default_days, 
        color=color, 
        requires_belt=requires_belt, 
        requires_weight=requires_weight
    )

def update(activity_id: int, name: str, default_days: list, color: str = None, requires_belt: bool = True, requires_weight: bool = True) -> None:
    """Update an existing activity."""
    # (Keep whatever validation you have here)
    
    activities_repo.update(
        activity_id=activity_id, 
        name=name, 
        default_days=default_days, 
        color=color, 
        requires_belt=requires_belt, 
        requires_weight=requires_weight
    )

def deactivate(activity_id: int) -> None:
    activities_repo.set_active(activity_id, False)
    try:
        from services import audit_service
        audit_service.record("activity.archive", target_type="activity", target_id=activity_id)
    except Exception:
        pass


def reactivate(activity_id: int) -> None:
    activities_repo.set_active(activity_id, True)
    try:
        from services import audit_service
        audit_service.record("activity.restore", target_type="activity", target_id=activity_id)
    except Exception:
        pass


def count_references(activity_id: int) -> int:
    """How many subscriptions reference this activity (for the delete
    confirmation message)."""
    return activities_repo.count_active_subscriptions(activity_id)

def count_active_references(activity_id: int) -> int:
    """Number of subscriptions for this activity with status='active'."""
    return activities_repo.count_active_subscriptions_by_status(activity_id)

def delete(activity_id: int) -> None:
    refs = count_references(activity_id)
    if refs > 0:
        raise ValueError("Cannot delete activity with existing subscriptions.")
    activities_repo.delete(activity_id)
    try:
        from services import audit_service
        audit_service.record("activity.delete", target_type="activity", target_id=activity_id)
    except Exception:
        pass
    
    
def get_weekly_attendance(activity_id: int, weeks: int = 8) -> list[dict]:
    """
    Returns attendance counts per week for the last N weeks.
    Output: [{"week_label": "Week 1", "count": 12}, ...]
    """
    import datetime
    from db.database import get_connection
    
    today = datetime.date.today()
    # Find the start of the current week (Monday)
    start_of_this_week = today - datetime.timedelta(days=today.weekday())
    
    results = []
    conn = get_connection()
    try:
        for i in range(weeks - 1, -1, -1):
            week_start = start_of_this_week - datetime.timedelta(weeks=i)
            week_end = week_start + datetime.timedelta(days=6)
            
            row = conn.execute(
                """
                SELECT COUNT(*) FROM attendance_log
                WHERE activity_id = ?
                  AND result = 'allowed'
                  AND substr(scan_datetime, 1, 10) >= ?
                  AND substr(scan_datetime, 1, 10) <= ?
                """,
                (activity_id, week_start.isoformat(), week_end.isoformat())
            ).fetchone()
            
            results.append({
                "week_label": week_start.strftime("%b %d"), # e.g. "Oct 14"
                "count": row[0] if row else 0,
            })
    finally:
        conn.close()
    
    return results


def get_monthly_revenue(activity_id: int, months: int = 6) -> list[dict]:
    """
    Returns revenue sums per month for the last N months.
    Output: [{"month_label": "May", "total": 1500.0}, ...]
    """
    import datetime
    import calendar
    from db.database import get_connection
    
    today = datetime.date.today()
    results = []
    conn = get_connection()
    try:
        for i in range(months - 1, -1, -1):
            # Calculate the year and month i months ago
            total_months = today.year * 12 + today.month - 1 - i
            y = total_months // 12
            m = (total_months % 12) + 1
            
            # Get first and last day of that month
            first_day = datetime.date(y, m, 1).isoformat()
            last_day = datetime.date(y, m, calendar.monthrange(y, m)[1]).isoformat()
            
            row = conn.execute(
                """
                SELECT COALESCE(SUM(p.amount), 0) 
                FROM payments p
                JOIN subscriptions s ON s.subscription_id = p.subscription_id
                WHERE s.activity_id = ?
                  AND p.payment_date >= ?
                  AND p.payment_date <= ?
                """,
                (activity_id, first_day, last_day)
            ).fetchone()
            
            results.append({
                "month_label": datetime.date(y, m, 1).strftime("%b"), # e.g. "May"
                "total": float(row[0]) if row else 0.0,
            })
    finally:
        conn.close()
    
    return results


def get_kpis(activity_id: int, date_from: str, date_to: str) -> dict:
    """Fetch the KPI numbers for a specific period."""
    from repositories import activities_repo
    return activities_repo.get_activity_kpis(activity_id, date_from, date_to)

def get_charts_data(activity_id: int) -> dict:
    """Fetch the chart data for the last 6 months and 8 weeks."""
    from repositories import activities_repo
    return activities_repo.get_activity_charts(activity_id)