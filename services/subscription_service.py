"""
Subscription service — expiry computation, status resolution, activation.

This is where "what does 'active' mean right now" is decided. Repos only
fetch/store rows; this module interprets them.
"""

import os
import sys
from datetime import date, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import get_plan, load_config
from models.subscription import Subscription
from repositories import subscriptions_repo


def compute_expiry_date(start_date: date, payment_date: date = None) -> date:
    """
    Computes expiry per the configured policy:
      - "thirty_days_from_payment": payment_date (or start_date) + 30 days.
      - "first_of_next_month": the 1st of the month following start_date.
    """
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
    allowed_days: list[str],
    start_date: date,
    activated_by: str,
    payment_amount: float,
    payment_date: date,
    plan_type: str = None,
) -> int:
    """
    Create a new subscription row.

    - activity_id: the activity this subscription is for
    - sessions_total: the open-ended count the receptionist entered
    - allowed_days: the specific days this player is authorized
      (defaults to the activity's default_days, but can be overridden)
    - plan_type: optional preset key for legacy reporting. NULL for custom.
    """
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
    """
    Records a payment against an EXISTING subscription. Recomputes expiry
    and reactivates unless the new expiry is already in the past.
    """
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


def get_active(player_id: int) -> "Subscription | None":
    """
    Returns the currently-valid subscription for a player, applying lazy
    expiry correction: if a stored-active row's expiry_date has passed,
    mark it expired and return None.
    """
    sub = subscriptions_repo.get_active_for_player(player_id)
    if sub is None:
        return None

    expiry = date.fromisoformat(sub.expiry_date)
    if date.today() >= expiry:
        subscriptions_repo.set_status(sub.subscription_id, "expired")
        return None

    return sub


def get_display_status(player_id: int) -> dict:
    """
    Single source of truth for "what is this player's subscription
    situation right now". Applies lazy-expiry correction.
    """
    active = subscriptions_repo.get_active_for_player(player_id)

    if active is not None:
        expiry = date.fromisoformat(active.expiry_date)
        if date.today() >= expiry:
            subscriptions_repo.set_status(active.subscription_id, "expired")
            return {
                "status": "expired",
                "subscription_id": active.subscription_id,
                "plan_type": active.plan_type,
                "sessions_remaining": active.sessions_remaining,
                "sessions_total": active.sessions_total,
                "expiry_date": active.expiry_date,
            }
        return {
            "status": "active",
            "subscription_id": active.subscription_id,
            "plan_type": active.plan_type,
            "sessions_remaining": active.sessions_remaining,
            "sessions_total": active.sessions_total,
            "expiry_date": active.expiry_date,
        }

    history = subscriptions_repo.get_history_for_player(player_id)
    if not history:
        return {"status": "none", "subscription_id": None, "plan_type": None,
                "sessions_remaining": None, "sessions_total": None,
                "expiry_date": None}

    latest = history[0]
    return {
        "status": latest.status,
        "subscription_id": latest.subscription_id,
        "plan_type": latest.plan_type,
        "sessions_remaining": latest.sessions_remaining,
        "sessions_total": latest.sessions_total,
        "expiry_date": latest.expiry_date,
    }


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