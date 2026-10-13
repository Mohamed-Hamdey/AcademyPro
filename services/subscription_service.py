"""
Subscription service — expiry computation, status resolution, activation.

A player may have multiple active subscriptions, one per activity. Each
has its own sessions count and allowed_days, and they decrement
independently.
"""

import os
import sys
from datetime import date, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import load_config
from models.subscription import Subscription
from repositories import subscriptions_repo


# ---------------------------------------------------------------------------
# Expiry + activation
# ---------------------------------------------------------------------------

def compute_expiry_date(start_date: date, payment_date: date = None) -> date:
    config = load_config()
    policy = config.get("expiry_policy", "thirty_days_from_payment")

    if policy == "first_of_next_month":
        if start_date.month == 12:
            return date(start_date.year + 1, 1, 1)
        return date(start_date.year, start_date.month + 1, 1)

    basis = payment_date or start_date
    return basis + timedelta(days=30)


def activate(
    player_id: int,
    activity_id: int,
    sessions_total: int,
    allowed_days: list,
    start_date: date,
    activated_by: str,
    payment_amount: float,
    payment_date: date,
    plan_type: str = None,
) -> int:
    if sessions_total <= 0:
        raise ValueError("Sessions count must be greater than zero")
    if not allowed_days:
        raise ValueError("At least one training day is required")

    expiry = compute_expiry_date(start_date, payment_date)

    sub = Subscription(
        subscription_id=None,
        player_id=player_id,
        activity_id=activity_id,
        plan_type=plan_type,
        start_date=start_date.isoformat(),
        expiry_date=expiry.isoformat(),
        sessions_total=sessions_total,
        sessions_remaining=sessions_total,
        allowed_days=allowed_days,
        status="active",
        activated_by=activated_by,
        payment_amount=payment_amount,
        payment_date=payment_date.isoformat(),
    )
    return subscriptions_repo.create(sub)


def record_payment(subscription_id: int, payment_amount: float, payment_date: date) -> None:
    sub = subscriptions_repo.get_by_id(subscription_id)
    if sub is None:
        return
    start = date.fromisoformat(sub.start_date)
    new_expiry = compute_expiry_date(start, payment_date)
    new_status = "active" if date.today() < new_expiry else "expired"
    subscriptions_repo.update_payment_and_expiry(
        subscription_id,
        payment_amount,
        payment_date.isoformat(),
        new_expiry.isoformat(),
        new_status,
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get_active(player_id: int) -> "Subscription | None":
    """
    The single 'current' subscription for a player — the most recent
    active one that hasn't expired. Kept for backward compatibility with
    code that only needs one (e.g. the check-in pipeline's default).

    Prefer get_all_active() when you need the full picture.
    """
    subs = get_all_active(player_id)
    return subs[0] if subs else None


def get_all_active(player_id: int) -> list[Subscription]:
    """
    Every currently-valid active subscription for a player.

    Applies lazy expiry: any stored-active row whose expiry_date has
    passed gets marked expired and excluded from the result.
    """
    rows = subscriptions_repo.get_all_active_for_player(player_id)
    today = date.today()
    result = []
    for sub in rows:
        expiry = date.fromisoformat(sub.expiry_date)
        if today >= expiry:
            subscriptions_repo.set_status(sub.subscription_id, "expired")
            continue
        result.append(sub)
    return result


def get_display_status(player_id: int) -> dict:
    """
    Compact status for the player list: one summary line per player.

    If a player has N active subscriptions, this returns aggregate
    sessions and a status that is 'active' if any sub is active.
    """
    subs = get_all_active(player_id)

    if subs:
        return {
            "status": "active",
            "subscription_id": subs[0].subscription_id,   # most recent
            "plan_type": subs[0].plan_type,               # most recent's plan
            "sessions_remaining": sum(s.sessions_remaining for s in subs),
            "sessions_total": sum(s.sessions_total for s in subs),
            "expiry_date": max(s.expiry_date for s in subs),  # latest expiry
            "active_count": len(subs),
        }

    # No active subs. Fall back to the latest historical sub so the player
    # list still shows a meaningful status (expired/suspended).
    history = subscriptions_repo.get_history_for_player(player_id)
    if not history:
        return {"status": "none", "subscription_id": None, "plan_type": None,
                "sessions_remaining": None, "sessions_total": None,
                "expiry_date": None, "active_count": 0}

    latest = history[0]
    return {
        "status": latest.status,
        "subscription_id": latest.subscription_id,
        "plan_type": latest.plan_type,
        "sessions_remaining": latest.sessions_remaining,
        "sessions_total": latest.sessions_total,
        "expiry_date": latest.expiry_date,
        "active_count": 0,
    }


def get_display_statuses(player_id: int) -> list[dict]:
    """
    One dict per active subscription. Used by the player detail screen
    to render a table of subscriptions.
    """
    subs = get_all_active(player_id)
    result = []
    for sub in subs:
        result.append({
            "subscription_id": sub.subscription_id,
            "activity_id": sub.activity_id,
            "plan_type": sub.plan_type,
            "sessions_remaining": sub.sessions_remaining,
            "sessions_total": sub.sessions_total,
            "expiry_date": sub.expiry_date,
            "allowed_days": sub.allowed_days,
            "status": "active",
        })
    return result


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def suspend(subscription_id: int) -> None:
    subscriptions_repo.set_status(subscription_id, "suspended")


def adjust_sessions(subscription_id: int, new_value: int) -> None:
    subscriptions_repo.set_sessions_remaining(subscription_id, new_value)


def decrement_session(subscription_id: int) -> None:
    subscriptions_repo.decrement_sessions(subscription_id)


def increment_session(subscription_id: int) -> None:
    subscriptions_repo.increment_sessions(subscription_id)


def get_history(player_id: int) -> list[Subscription]:
    return subscriptions_repo.get_history_for_player(player_id)


def mark_expired(subscription_id: int) -> None:
    subscriptions_repo.set_status(subscription_id, "expired")