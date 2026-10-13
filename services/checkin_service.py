"""
Check-in service — the single pipeline for validating, logging, and
decrementing a check-in.

Policy: a player may be checked in at most once per calendar day.
A second scan of the same player on the same day is refused with a
"already checked in today" outcome; no attendance row is logged and no
session is decremented.

The DenyPopup is a UI concern. This service accepts a parent_widget
parameter purely so the caller can pass it through to the popup — the
service itself does not import UI modules besides that one.
"""

import os
import sys
from datetime import date
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.player import Player
from models.subscription import Subscription
from repositories import players_repo
from services import subscription_service, attendance_service
from logic.validation import validate_check_in
from ui.dialogs.deny_popup import DenyPopup
from ui.i18n import t
from app_state import app as app_state


# Legacy constant kept for backward compatibility with v1 callers.
# New code should rely on the current logged-in user instead.
RECORDED_BY = "reception"


def _current_recorder() -> str:
    """The username to record on attendance rows. Falls back to 'system'
    if somehow called before login (shouldn't happen in normal flow)."""
    return app_state.recorded_by() or "system"

def _translate_reason(raw_reason: str) -> str:
    """Map validation-layer English reason to a localized string."""
    r = (raw_reason or "").lower()
    if "not a training day" in r:
        if "allowed:" in r:
            days = raw_reason.split("allowed:", 1)[1].strip().rstrip(")")
            return t("reason.not_a_training_day", days=days)
        return raw_reason
    if "no sessions" in r:
        return t("reason.no_sessions")
    if "expired" in r:
        return t("reason.expired")
    if "suspended" in r:
        return t("reason.suspended")
    if "no subscription" in r or "no active subscription" in r:
        return t("reason.no_subscription")
    return raw_reason


@dataclass
class CheckInOutcome:
    player: Player
    subscription: Optional[Subscription]
    checked_in: bool
    reason: Optional[str]
    was_override: bool
    was_duplicate: bool = False


def perform_check_in(
    player_id: int,
    parent_widget=None,
    recorded_by: str = None,
) -> Optional[CheckInOutcome]:
    """
    Runs the full pipeline for one player_id.

    Returns None if the player doesn't exist.
    Returns an outcome with was_duplicate=True if already checked in today.
    """
    player = players_repo.get_by_id(player_id)
    if recorded_by is None:
        recorded_by = _current_recorder()

    # Once-per-day guard
    # Once-per-day guard
    if attendance_service.has_checked_in_today(player_id, on_date=date.today()):
        return CheckInOutcome(
            player=player,
            subscription=None,
            checked_in=True,
            reason=None,
            was_override=False,
            was_duplicate=True,
        )

    result = validate_check_in(player_id, date.today())

    if result.allowed:
        sub_id = result.subscription.subscription_id
        attendance_service.log_attendance(player_id, sub_id, "allowed", None, recorded_by)
        subscription_service.decrement_session(sub_id)
        result.subscription.sessions_remaining = max(
            0, result.subscription.sessions_remaining - 1
        )
        return CheckInOutcome(
            player=player, subscription=result.subscription,
            checked_in=True, reason=None, was_override=False,
        )

    popup = DenyPopup(player.full_name, _translate_reason(result.reason), parent_widget)
    popup.exec()
    was_override, note = popup.result_data()

    sub_id = result.subscription.subscription_id if result.subscription else None

    if was_override:
        attendance_service.log_attendance(
            player_id, sub_id, "allowed", None, recorded_by,
            was_override=True, override_note=note,
        )
        if sub_id is not None:
            subscription_service.decrement_session(sub_id)
            if result.subscription is not None:
                result.subscription.sessions_remaining = max(
                    0, result.subscription.sessions_remaining - 1
                )
        return CheckInOutcome(
            player=player, subscription=result.subscription,
            checked_in=True, reason=None, was_override=True,
        )
    from services import audit_service
    audit_service.checkin_override(player_id=player_id, note=note)

    attendance_service.log_attendance(
        player_id, sub_id, "denied", result.reason, recorded_by
    )
    return CheckInOutcome(
        player=player, subscription=result.subscription,
        checked_in=False, reason=result.reason, was_override=False,
    )