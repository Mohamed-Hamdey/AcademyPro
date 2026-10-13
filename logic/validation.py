"""
Core check-in validation logic.

Now supports multiple active subscriptions per player. A "valid" sub is
one that:
  * is stored-active AND hasn't passed expiry
  * has sessions remaining
  * allows today's weekday

If a player has 2+ valid subs today, the caller decides which one to use.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import subscription_service
from models.subscription import Subscription


@dataclass
class CheckInResult:
    allowed: bool
    reason: Optional[str]
    subscription: Optional[Subscription]              # the picked sub (if allowed)
    valid_subscriptions: list = field(default_factory=list)   # all valid today
    all_active_count: int = 0


def validate_check_in(player_id: int, today: date) -> CheckInResult:
    """
    Check whether the player can check in today, against any of their
    active subscriptions.

    Returns:
      allowed=True + subscription=<the chosen one> if at least one valid
      allowed=False + reason=<why> otherwise
    """
    active = subscription_service.get_all_active(player_id)
    all_active_count = len(active)

    if not active:
        # Distinguish "never had a subscription" from "expired/suspended"
        history = subscription_service.get_history(player_id)
        if history and history[0].status == "expired":
            return CheckInResult(
                allowed=False,
                reason="Subscription expired",
                subscription=history[0],
                all_active_count=0,
            )
        return CheckInResult(
            allowed=False,
            reason="No active subscription",
            subscription=None,
            all_active_count=0,
        )

    # Filter the active subs by whether they permit today and have sessions.
    today_name = today.strftime("%A")

    # Partition subs into "valid today" vs. reasons they don't qualify
    valid = []
    no_sessions = []
    wrong_day = []

    for sub in active:
        if sub.sessions_remaining <= 0:
            no_sessions.append(sub)
            continue
        if today_name not in (sub.allowed_days or []):
            wrong_day.append(sub)
            continue
        valid.append(sub)

    if valid:
        # Auto-pick the first (most recent by subscription_id DESC).
        # In a later batch, the UI will offer a picker when len(valid) > 1.
        return CheckInResult(
            allowed=True,
            reason=None,
            subscription=valid[0],
            valid_subscriptions=valid,
            all_active_count=all_active_count,
        )

    # Nothing valid. Return the most relevant reason.
    if no_sessions and not wrong_day:
        return CheckInResult(
            allowed=False,
            reason="No sessions remaining",
            subscription=no_sessions[0],
            all_active_count=all_active_count,
        )

    if wrong_day:
        # Show the first wrong-day sub's allowed days in the message
        sub = wrong_day[0]
        allowed_days_str = ", ".join(sub.allowed_days or [])
        return CheckInResult(
            allowed=False,
            reason=f"Not a training day for this plan (allowed: {allowed_days_str})",
            subscription=sub,
            all_active_count=all_active_count,
        )

    # No sessions and wrong day — default to no-sessions reason
    return CheckInResult(
        allowed=False,
        reason="No sessions remaining",
        subscription=no_sessions[0] if no_sessions else active[0],
        all_active_count=all_active_count,
    )