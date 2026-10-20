"""
Subscription service — expiry computation, status resolution, activation.

A player may have multiple active subscriptions, one per activity. Each
has its own sessions count and allowed_days, and they decrement
independently.
"""

import os
import sys
from datetime import date, timedelta
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import load_config
from models.subscription import Subscription
from repositories import subscriptions_repo
from db.database import get_connection

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
    new_sub_id = subscriptions_repo.create(sub)

    if payment_amount and payment_amount > 0:
        try:
            from services import payment_service
            payment_service.record(
                player_id=player_id,
                amount=payment_amount,
                payment_date=payment_date,
                subscription_id=new_sub_id,
                method="cash",
                notes="Initial subscription payment",
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to log initial payment"
            )

    # Audit: subscription activation (initial creation).
    try:
        from services import audit_service
        audit_service.record(
            "subscription.activate",
            target_type="subscription",
            target_id=new_sub_id,
            details={
                "player_id": player_id,
                "activity_id": activity_id,
                "sessions": sessions_total,
                "payment_amount": payment_amount,
            },
        )
    except Exception:
        logging.getLogger(__name__).exception(
            "Audit: failed to log subscription.activate"
        )

    return new_sub_id


def record_payment(subscription_id: int, payment_amount: float, payment_date: date) -> None:
    """
    Record a payment against an EXISTING subscription. Two things happen:

    1. A ledger row is inserted into `payments` (source of truth).
    2. The subscription row's denormalized `payment_amount` / `payment_date`
       are updated for backwards compatibility, and expiry is recomputed.
    """
    sub = subscriptions_repo.get_by_id(subscription_id)
    if sub is None:
        return

    # 1. Ledger entry
    try:
        from services import payment_service
        payment_service.record(
            player_id=sub.player_id,
            amount=payment_amount,
            payment_date=payment_date,
            subscription_id=subscription_id,
            method="cash",
            notes="Subscription payment",
        )
    except Exception:
        
        logging.getLogger(__name__).exception(
            "Failed to log ledger entry"
        )

    # 2. Update subscription row (denormalized copy + expiry)
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
        # Audit: renewal / payment record.
    try:
        from services import audit_service
        audit_service.record(
            "subscription.record_payment",
            target_type="subscription",
            target_id=subscription_id,
            details={
                "player_id": sub.player_id,
                "amount": payment_amount,
                "new_expiry": new_expiry.isoformat(),
            },
        )
    except Exception:
        logging.getLogger(__name__).exception(
            "Audit: failed to log subscription.record_payment"
        )


def update(
    subscription_id: int,
    *,
    activity_id: int,
    sessions_total: int,
    allowed_days: list,
    start_date: date,
    payment_amount: float,
    payment_date: date,
) -> None:
    """
    Update every editable field of a subscription.

    Recomputes expiry from start_date + payment_date. Adjusts
    sessions_remaining when sessions_total changes (delta is added to
    the remaining count — so 8→12 with 4 remaining becomes 8 remaining).

    If payment_amount or payment_date changed, the linked payment
    ledger row is updated in place. Every change is logged to the audit
    log with old→new values.
    """
    from services import audit_service

    if sessions_total <= 0:
        raise ValueError("Sessions count must be greater than zero")
    if not allowed_days:
        raise ValueError("At least one training day is required")
    if payment_amount is not None and payment_amount < 0:
        raise ValueError("Payment amount cannot be negative")

    existing = subscriptions_repo.get_by_id(subscription_id)
    if existing is None:
        raise ValueError("Subscription not found")

    # Capture old values for the audit diff.
    old = {
        "activity_id": existing.activity_id,
        "sessions_total": existing.sessions_total,
        "sessions_remaining": existing.sessions_remaining,
        "allowed_days": list(existing.allowed_days or []),
        "start_date": existing.start_date,
        "expiry_date": existing.expiry_date,
        "payment_amount": existing.payment_amount,
        "payment_date": existing.payment_date,
    }

    # Recompute expiry from the same policy activate() uses.
    new_expiry = compute_expiry_date(start_date, payment_date)

    # Adjust sessions_remaining by the delta in sessions_total.
    delta = sessions_total - existing.sessions_total
    new_remaining = max(0, existing.sessions_remaining + delta)

    # Write the row.
    subscriptions_repo.update_fields(
        subscription_id,
        activity_id=activity_id,
        sessions_total=sessions_total,
        allowed_days=allowed_days,
        start_date=start_date.isoformat(),
        expiry_date=new_expiry.isoformat(),
        payment_amount=payment_amount,
        payment_date=payment_date.isoformat(),
    )
    # Set the adjusted remaining in a separate call — update_fields
    # doesn't touch it to keep that function pure.
    subscriptions_repo.set_sessions_remaining(subscription_id, new_remaining)

    # Sync the ledger row if the payment changed.
    if (
        existing.payment_amount != payment_amount
        or existing.payment_date != payment_date.isoformat()
    ):
        try:
            _sync_payment_ledger_row(
                subscription_id=subscription_id,
                player_id=existing.player_id,
                new_amount=payment_amount,
                new_date=payment_date,
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to sync payment ledger row for subscription %s",
                subscription_id,
            )

    # Build the audit diff (only fields that actually changed).
    new = {
        "activity_id": activity_id,
        "sessions_total": sessions_total,
        "sessions_remaining": new_remaining,
        "allowed_days": list(allowed_days or []),
        "start_date": start_date.isoformat(),
        "expiry_date": new_expiry.isoformat(),
        "payment_amount": payment_amount,
        "payment_date": payment_date.isoformat(),
    }
    changes = {
        k: {"from": old[k], "to": new[k]}
        for k in new
        if old[k] != new[k]
    }
    if changes:
        audit_service.record(
            "subscription.update",
            target_type="subscription",
            target_id=subscription_id,
            details={"changes": changes, "player_id": existing.player_id},
        )


def _sync_payment_ledger_row(
    subscription_id: int,
    player_id: int,
    new_amount: float,
    new_date: date,
) -> None:
    """
    Update the most recent payment row that's linked to this
    subscription, so the ledger reflects the new amount/date.

    If no ledger row exists (edge case — older data), create one.
    """
    from repositories import payments_repo

    rows = payments_repo.list_for_subscription(subscription_id)
    if rows:
        # Update the most recent row (highest payment_id).
        latest = max(rows, key=lambda p: p.payment_id or 0)
        conn = get_connection()
        try:
            conn.execute(
                """
                UPDATE payments
                SET amount = ?, payment_date = ?
                WHERE payment_id = ?
                """,
                (new_amount, new_date.isoformat(), latest.payment_id),
            )
            conn.commit()
        finally:
            conn.close()
    else:
        # No ledger entry — create one so the totals are correct.
        from services import payment_service
        payment_service.record(
            player_id=player_id,
            amount=new_amount,
            payment_date=new_date,
            subscription_id=subscription_id,
            method="cash",
            notes="Subscription payment (created during edit)",
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

def get_display_status_bulk(player_ids: list[int]) -> dict[int, dict]:
    """
    Batched version of get_display_status. One DB call for many players.
    Applies the same lazy-expiry logic and returns the same shape per player.
    """
    from datetime import date as _date
    subs_map = subscriptions_repo.get_all_active_for_players(player_ids)
    today = _date.today()
    result = {}

    for pid in player_ids:
        subs = subs_map.get(pid, [])
        # Apply lazy expiry
        valid = []
        for s in subs:
            exp = _date.fromisoformat(s.expiry_date)
            if today >= exp:
                subscriptions_repo.set_status(s.subscription_id, "expired")
                continue
            valid.append(s)

        if valid:
            result[pid] = {
                "status": "active",
                "subscription_id": valid[0].subscription_id,
                "plan_type": valid[0].plan_type,
                "sessions_remaining": sum(s.sessions_remaining for s in valid),
                "sessions_total": sum(s.sessions_total for s in valid),
                "expiry_date": max(s.expiry_date for s in valid),
                "active_count": len(valid),
            }
        else:
            # Fall back to the latest historical sub.
            hist = subscriptions_repo.get_history_for_player(pid)
            if hist:
                latest = hist[0]
                result[pid] = {
                    "status": latest.status,
                    "subscription_id": latest.subscription_id,
                    "plan_type": latest.plan_type,
                    "sessions_remaining": latest.sessions_remaining,
                    "sessions_total": latest.sessions_total,
                    "expiry_date": latest.expiry_date,
                    "active_count": 0,
                }
            else:
                result[pid] = {
                    "status": "none", "subscription_id": None,
                    "plan_type": None, "sessions_remaining": None,
                    "sessions_total": None, "expiry_date": None,
                    "active_count": 0,
                }
    return result
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

def get_suspended(player_id: int) -> list[Subscription]:
    """Suspended (but not archived) subscriptions for a player."""
    return subscriptions_repo.get_suspended_for_player(player_id)
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
    try:
        from services import audit_service
        audit_service.record(
            "subscription.suspend",
            target_type="subscription",
            target_id=subscription_id,
        )
    except Exception:
        logging.getLogger(__name__).exception(
            "Audit: failed to log subscription.suspend"
        )


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
    try:
        from services import audit_service
        audit_service.record(
            "subscription.expire",
            target_type="subscription",
            target_id=subscription_id,
        )
    except Exception:
        logging.getLogger(__name__).exception(
            "Audit: failed to log subscription.expire"
        )