"""
Expense service — CRUD + aggregations for the expenses ledger.

Fixed set of categories so totals roll up cleanly. Not freeform.
"""

import os
import sys
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from repositories import expenses_repo
from repositories.expenses_repo import Expense
from app_state import app as app_state


# Canonical category keys. The UI shows a translation for each.
CATEGORIES = ["rent", "salaries", "equipment", "utilities", "other"]


def create(category: str, description: str, amount: float,
           expense_date: date, currency: str = "EGP") -> int:
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category: {category}")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")
    if not description or not description.strip():
        raise ValueError("Description is required")

    e = Expense(
        expense_id=None,
        category=category,
        description=description.strip(),
        amount=amount,
        currency=currency,
        expense_date=expense_date.isoformat(),
        recorded_by=app_state.recorded_by(),
    )
    return expenses_repo.create(e)


def update(expense_id: int, category: str, description: str,
           amount: float, expense_date: date, currency: str = "EGP") -> None:
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category: {category}")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")
    if not description or not description.strip():
        raise ValueError("Description is required")

    e = expenses_repo.get_by_id(expense_id)
    if e is None:
        raise ValueError("Expense not found")

    e.category = category
    e.description = description.strip()
    e.amount = amount
    e.currency = currency
    e.expense_date = expense_date.isoformat()
    expenses_repo.update(e)


def delete(expense_id: int) -> None:
    expenses_repo.delete(expense_id)


def get(expense_id: int) -> Expense | None:
    return expenses_repo.get_by_id(expense_id)


def list_for_range(date_from: date, date_to: date) -> list[Expense]:
    return expenses_repo.list_for_date_range(date_from.isoformat(), date_to.isoformat())


def list_for_day(d: date) -> list[Expense]:
    iso = d.isoformat()
    return expenses_repo.list_for_date_range(iso, iso)


def list_for_month(year: int, month: int) -> list[Expense]:
    import calendar
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return list_for_range(first, last)


def total_for_day(d: date) -> float:
    iso = d.isoformat()
    return expenses_repo.total_for_date_range(iso, iso)


def total_for_month(year: int, month: int) -> float:
    import calendar
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return expenses_repo.total_for_date_range(first.isoformat(), last.isoformat())


def total_by_category_for_month(year: int, month: int) -> list[dict]:
    import calendar
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return expenses_repo.total_by_category(first.isoformat(), last.isoformat())