"""
Payment service — records payments into the ledger and queries totals.

Payments are the source of truth for revenue reporting. Each payment row
is one transaction; refunds are negative amounts.
"""

import os
import sys
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from repositories import payments_repo
from repositories.payments_repo import Payment
from app_state import app as app_state


def record(player_id: int,
           amount: float,
           payment_date: date,
           subscription_id: int = None,
           method: str = "cash",
           notes: str = None,
           currency: str = "EGP") -> int:
    """
    Record a payment (or refund if amount is negative).

    Returns the new payment_id.
    """
    if amount == 0:
        raise ValueError("Amount cannot be zero")

    recorded_by = app_state.recorded_by()

    p = Payment(
        payment_id=None,
        player_id=player_id,
        subscription_id=subscription_id,
        amount=amount,
        currency=currency,
        method=method,
        payment_date=payment_date.isoformat(),
        receipt_no=None,
        notes=notes,
        recorded_by=recorded_by,
    )
    return payments_repo.create(p)


def list_for_player(player_id: int) -> list[Payment]:
    return payments_repo.list_for_player(player_id)


def list_for_subscription(subscription_id: int) -> list[Payment]:
    return payments_repo.list_for_subscription(subscription_id)


def list_recent_with_names(limit: int = 20) -> list[dict]:
    return payments_repo.list_recent_with_names(limit=limit)


def total_for_day(d: date) -> float:
    iso = d.isoformat()
    return payments_repo.total_for_date_range(iso, iso)


def total_for_month(year: int, month: int) -> float:
    import calendar
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return payments_repo.total_for_date_range(first.isoformat(), last.isoformat())


def total_for_range(start: date, end: date) -> float:
    return payments_repo.total_for_date_range(start.isoformat(), end.isoformat())


def total_by_activity_for_day(d: date) -> list[dict]:
    iso = d.isoformat()
    return payments_repo.total_by_activity(iso, iso)


def total_by_activity_for_range(start: date, end: date) -> list[dict]:
    return payments_repo.total_by_activity(start.isoformat(), end.isoformat())