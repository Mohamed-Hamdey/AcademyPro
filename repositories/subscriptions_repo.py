"""
Subscriptions repository — all SQL touching the `subscriptions` table.

No business logic here. Whether a subscription is "expired" or "suspended"
is decided by services/subscription_service.py, not in this file.
"""

import os
import sys
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection
from models.subscription import Subscription


def create(subscription: Subscription) -> int:
    """
    Insert a fully-formed Subscription row. Caller is responsible for
    having already computed expiry_date and status.
    """
    import json
    allowed_days_json = json.dumps(subscription.allowed_days or [])

    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO subscriptions
                (player_id, activity_id, plan_type, start_date, expiry_date,
                 sessions_total, sessions_remaining, allowed_days, status,
                 activated_by, payment_amount, payment_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subscription.player_id,
                subscription.activity_id,
                subscription.plan_type,
                subscription.start_date,
                subscription.expiry_date,
                subscription.sessions_total,
                subscription.sessions_remaining,
                allowed_days_json,
                subscription.status,
                subscription.activated_by,
                subscription.payment_amount,
                subscription.payment_date,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
def get_by_id(subscription_id: int) -> Optional[Subscription]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE subscription_id = ?",
            (subscription_id,),
        ).fetchone()
        return Subscription.from_row(row) if row else None
    finally:
        conn.close()

def get_all_active_for_player(player_id: int) -> list[Subscription]:
    """
    All subscriptions for a player whose stored status is 'active'.
    Does NOT check expiry_date — the service layer filters those.

    Ordered by start_date DESC so the most-recently-activated sub is
    first. That's the order the check-in pipeline uses to auto-pick when
    there's exactly one valid sub today.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE player_id = ? AND status = 'active'
            ORDER BY start_date DESC, subscription_id DESC
            """,
            (player_id,),
        ).fetchall()
        return [Subscription.from_row(r) for r in rows]
    finally:
        conn.close()
def get_active_for_player(player_id: int) -> Optional[Subscription]:
    """
    Most recent subscription whose stored status is 'active'.
    Note: does NOT check expiry_date — the service layer decides whether
    a stored-active row is actually expired.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE player_id = ? AND status = 'active'
            ORDER BY start_date DESC
            LIMIT 1
            """,
            (player_id,),
        ).fetchone()
        return Subscription.from_row(row) if row else None
    finally:
        conn.close()


def get_history_for_player(player_id: int) -> list[Subscription]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE player_id = ?
            ORDER BY start_date DESC
            """,
            (player_id,),
        ).fetchall()
        return [Subscription.from_row(r) for r in rows]
    finally:
        conn.close()


def set_status(subscription_id: int, status: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE subscriptions SET status = ? WHERE subscription_id = ?",
            (status, subscription_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_sessions_remaining(subscription_id: int, value: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE subscriptions SET sessions_remaining = ? WHERE subscription_id = ?",
            (value, subscription_id),
        )
        conn.commit()
    finally:
        conn.close()


def decrement_sessions(subscription_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE subscriptions
            SET sessions_remaining = sessions_remaining - 1
            WHERE subscription_id = ? AND sessions_remaining > 0
            """,
            (subscription_id,),
        )
        conn.commit()
    finally:
        conn.close()


def increment_sessions(subscription_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE subscriptions
            SET sessions_remaining = sessions_remaining + 1
            WHERE subscription_id = ?
            """,
            (subscription_id,),
        )
        conn.commit()
    finally:
        conn.close()


def update_payment_and_expiry(
    subscription_id: int,
    payment_amount: float,
    payment_date: str,
    new_expiry: str,
    new_status: str,
) -> None:
    """Used by update_subscription_payment — passes pre-computed values."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE subscriptions
            SET payment_amount = ?, payment_date = ?, expiry_date = ?, status = ?
            WHERE subscription_id = ?
            """,
            (payment_amount, payment_date, new_expiry, new_status, subscription_id),
        )
        conn.commit()
    finally:
        conn.close()