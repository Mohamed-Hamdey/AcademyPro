"""
Payments repository — SQL for the payments ledger.

Every payment (and refund, as a negative amount) is a row here. This is
the source of truth for revenue reporting.
"""

import os
import sys
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection


@dataclass
class Payment:
    payment_id: Optional[int]
    player_id: int
    subscription_id: Optional[int]
    amount: float
    currency: str
    method: str
    payment_date: str        # ISO date
    receipt_no: Optional[str]
    notes: Optional[str]
    recorded_by: str
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "Payment":
        return cls(
            payment_id=row["payment_id"],
            player_id=row["player_id"],
            subscription_id=row["subscription_id"],
            amount=row["amount"],
            currency=row["currency"] or "EGP",
            method=row["method"] or "cash",
            payment_date=row["payment_date"],
            receipt_no=row["receipt_no"],
            notes=row["notes"],
            recorded_by=row["recorded_by"],
            created_at=row["created_at"],
        )


def create(payment: Payment) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO payments
                (player_id, subscription_id, amount, currency, method,
                 payment_date, receipt_no, notes, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment.player_id,
                payment.subscription_id,
                payment.amount,
                payment.currency,
                payment.method,
                payment.payment_date,
                payment.receipt_no,
                payment.notes,
                payment.recorded_by,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_by_id(payment_id: int) -> Optional[Payment]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM payments WHERE payment_id = ?", (payment_id,)
        ).fetchone()
        return Payment.from_row(row) if row else None
    finally:
        conn.close()


def list_for_player(player_id: int) -> list[Payment]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM payments
            WHERE player_id = ?
            ORDER BY payment_date DESC, payment_id DESC
            """,
            (player_id,),
        ).fetchall()
        return [Payment.from_row(r) for r in rows]
    finally:
        conn.close()


def list_for_subscription(subscription_id: int) -> list[Payment]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM payments
            WHERE subscription_id = ?
            ORDER BY payment_date DESC, payment_id DESC
            """,
            (subscription_id,),
        ).fetchall()
        return [Payment.from_row(r) for r in rows]
    finally:
        conn.close()


def list_for_date_range(date_from: str, date_to: str) -> list[Payment]:
    """All payments with payment_date in [date_from, date_to]."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM payments
            WHERE payment_date >= ? AND payment_date <= ?
            ORDER BY payment_date DESC, payment_id DESC
            """,
            (date_from, date_to),
        ).fetchall()
        return [Payment.from_row(r) for r in rows]
    finally:
        conn.close()


def list_recent_with_names(limit: int = 20) -> list[dict]:
    """
    Payments joined with player name, newest first. Used by the daily
    dashboard's payments list.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT p.*, pl.full_name
            FROM payments p
            JOIN players pl ON pl.player_id = p.player_id
            ORDER BY p.payment_date DESC, p.payment_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def total_for_date_range(date_from: str, date_to: str) -> float:
    """Sum of amount for payments in [date_from, date_to]."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) FROM payments
            WHERE payment_date >= ? AND payment_date <= ?
            """,
            (date_from, date_to),
        ).fetchone()
        return float(row[0]) if row else 0.0
    finally:
        conn.close()


def total_by_activity(date_from: str, date_to: str) -> list[dict]:
    """
    Sum of payments grouped by activity, for the date range.
    Only includes payments tied to a subscription with an activity_id.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT s.activity_id,
                   COALESCE(SUM(p.amount), 0) AS total,
                   COUNT(p.payment_id)        AS count
            FROM payments p
            LEFT JOIN subscriptions s ON s.subscription_id = p.subscription_id
            WHERE p.payment_date >= ? AND p.payment_date <= ?
              AND s.activity_id IS NOT NULL
            GROUP BY s.activity_id
            ORDER BY total DESC
            """,
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def total_by_method(date_from: str, date_to: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT method, COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count
            FROM payments
            WHERE payment_date >= ? AND payment_date <= ?
            GROUP BY method
            ORDER BY total DESC
            """,
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete(payment_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM payments WHERE payment_id = ?", (payment_id,))
        conn.commit()
    finally:
        conn.close()