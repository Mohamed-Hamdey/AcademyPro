"""
Subscriptions repository — all SQL touching the `subscriptions` table.

No business logic here. Whether a subscription is "expired" or "suspended"
is decided by services/subscription_service.py, not in this file.

Soft-delete: subscriptions with `archived_at IS NOT NULL` are excluded
from all read paths. Use `list_archived()` to see them; use
`archive()`/`restore()` to change the flag.
"""

import os
import sys
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection
from models.subscription import Subscription


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_by_id(subscription_id: int) -> Optional[Subscription]:
    """
    Fetch a subscription by id, regardless of archived state. Used by
    archive/restore operations and by the edit dialog.
    """
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
    Excludes archived rows.

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
            WHERE player_id = ? AND status = 'active' AND archived_at IS NULL
            ORDER BY start_date DESC, subscription_id DESC
            """,
            (player_id,),
        ).fetchall()
        return [Subscription.from_row(r) for r in rows]
    finally:
        conn.close()


def get_active_for_player(player_id: int) -> Optional[Subscription]:
    """
    Most recent non-archived subscription whose stored status is 'active'.
    Note: does NOT check expiry_date — the service layer decides whether
    a stored-active row is actually expired.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE player_id = ? AND status = 'active' AND archived_at IS NULL
            ORDER BY start_date DESC
            LIMIT 1
            """,
            (player_id,),
        ).fetchone()
        return Subscription.from_row(row) if row else None
    finally:
        conn.close()


def get_all_active_for_players(player_ids: list[int]) -> dict[int, list[Subscription]]:
    """
    Batch version of get_all_active_for_player — one query for many players.
    Excludes archived rows. Returns {player_id: [Subscription, ...]}.
    """
    if not player_ids:
        return {}

    placeholders = ",".join("?" * len(player_ids))
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT * FROM subscriptions
            WHERE player_id IN ({placeholders})
              AND status = 'active'
              AND archived_at IS NULL
            ORDER BY start_date DESC, subscription_id DESC
            """,
            player_ids,
        ).fetchall()
    finally:
        conn.close()

    result = {pid: [] for pid in player_ids}
    for r in rows:
        s = Subscription.from_row(r)
        result.setdefault(s.player_id, []).append(s)
    return result

def get_suspended_for_player(player_id: int) -> list[Subscription]:
    """
    Suspended (but not archived) subscriptions for a player.

    Suspended subs are still visible in the player detail's subscription
    table — they're just marked as inactive. This function is used by
    the detail screen to render them alongside active subs.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE player_id = ? AND status = 'suspended' AND archived_at IS NULL
            ORDER BY start_date DESC, subscription_id DESC
            """,
            (player_id,),
        ).fetchall()
        return [Subscription.from_row(r) for r in rows]
    finally:
        conn.close()
def get_history_for_player(player_id: int) -> list[Subscription]:
    """
    All non-archived subscriptions for a player, most recent first.
    Includes expired and suspended — this is the full history.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE player_id = ? AND archived_at IS NULL
            ORDER BY start_date DESC
            """,
            (player_id,),
        ).fetchall()
        return [Subscription.from_row(r) for r in rows]
    finally:
        conn.close()


def list_archived() -> list[Subscription]:
    """All subscriptions that have been soft-deleted, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM subscriptions "
            "WHERE archived_at IS NOT NULL "
            "ORDER BY archived_at DESC"
        ).fetchall()
        return [Subscription.from_row(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

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
            "UPDATE subscriptions SET sessions_remaining = ? "
            "WHERE subscription_id = ?",
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
            (payment_amount, payment_date, new_expiry, new_status,
             subscription_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_fields(
    subscription_id: int,
    *,
    activity_id,
    sessions_total,
    allowed_days,
    start_date,
    expiry_date,
    payment_amount,
    payment_date,
):
    """
    Update the editable fields of a subscription in one statement.
    Called by subscription_service.update(). Does not adjust
    sessions_remaining — that's the service's job.
    """
    import json
    allowed_days_json = json.dumps(allowed_days or [])

    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE subscriptions
            SET activity_id = ?,
                sessions_total = ?,
                allowed_days = ?,
                start_date = ?,
                expiry_date = ?,
                payment_amount = ?,
                payment_date = ?
            WHERE subscription_id = ?
            """,
            (
                activity_id,
                sessions_total,
                allowed_days_json,
                start_date,
                expiry_date,
                payment_amount,
                payment_date,
                subscription_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------

def archive(subscription_id: int) -> None:
    """Soft-delete: stamp archived_at with the current timestamp."""
    from datetime import datetime
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE subscriptions SET archived_at = ? "
            "WHERE subscription_id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), subscription_id),
        )
        conn.commit()
    finally:
        conn.close()


def restore(subscription_id: int) -> None:
    """Un-archive: clear archived_at."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE subscriptions SET archived_at = NULL "
            "WHERE subscription_id = ?",
            (subscription_id,),
        )
        conn.commit()
    finally:
        conn.close()