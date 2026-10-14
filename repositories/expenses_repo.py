"""
Expenses repository — SQL for the expenses table.
"""

import os
import sys
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection


@dataclass
class Expense:
    expense_id: Optional[int]
    category: str
    description: str
    amount: float
    currency: str
    expense_date: str
    recorded_by: str
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "Expense":
        return cls(
            expense_id=row["expense_id"],
            category=row["category"],
            description=row["description"],
            amount=row["amount"],
            currency=row["currency"] or "EGP",
            expense_date=row["expense_date"],
            recorded_by=row["recorded_by"],
            created_at=row["created_at"],
        )


def create(expense: Expense) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO expenses
                (category, description, amount, currency, expense_date, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                expense.category,
                expense.description,
                expense.amount,
                expense.currency,
                expense.expense_date,
                expense.recorded_by,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_by_id(expense_id: int) -> Optional[Expense]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM expenses WHERE expense_id = ?", (expense_id,)
        ).fetchone()
        return Expense.from_row(row) if row else None
    finally:
        conn.close()


def update(expense: Expense) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE expenses
            SET category = ?, description = ?, amount = ?, currency = ?,
                expense_date = ?
            WHERE expense_id = ?
            """,
            (
                expense.category,
                expense.description,
                expense.amount,
                expense.currency,
                expense.expense_date,
                expense.expense_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def delete(expense_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM expenses WHERE expense_id = ?", (expense_id,))
        conn.commit()
    finally:
        conn.close()


def list_for_date_range(date_from: str, date_to: str) -> list[Expense]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM expenses
            WHERE expense_date >= ? AND expense_date <= ?
            ORDER BY expense_date DESC, expense_id DESC
            """,
            (date_from, date_to),
        ).fetchall()
        return [Expense.from_row(r) for r in rows]
    finally:
        conn.close()


def total_for_date_range(date_from: str, date_to: str) -> float:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) FROM expenses
            WHERE expense_date >= ? AND expense_date <= ?
            """,
            (date_from, date_to),
        ).fetchone()
        return float(row[0]) if row else 0.0
    finally:
        conn.close()


def total_by_category(date_from: str, date_to: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT category,
                   COALESCE(SUM(amount), 0) AS total,
                   COUNT(*) AS count
            FROM expenses
            WHERE expense_date >= ? AND expense_date <= ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()