"""
Check-in service — the single pipeline for validating, logging, and
decrementing a check-in.

Policy: a player may be checked in at most once per calendar day.

Session-activity model: the scan screen can be set to a specific activity
("Karate session"), in which case only subscriptions for that activity
are considered. Or it can be left on "Auto", in which case:
  * 1 valid sub → auto-selected
  * 2+ valid subs → caller shows the picker popup

When the receptionist has set a specific activity and the scanned player
isn't enrolled in it, we don't fall through to the deny popup — we return
an outcome flagged with `not_enrolled_in_activity=True` and let the scan
screen show a clear message.
"""

import os
import sys
from datetime import date
from dataclasses import dataclass, field
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


RECORDED_BY = "reception"


def _current_recorder() -> str:
    return app_state.recorded_by() or "system"


def _translate_reason(raw_reason: str) -> str:
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
    valid_subscriptions: list = field(default_factory=list)
    # True when 2+ subs are valid today and the caller must present a
    # picker before the check-in is committed. Nothing was logged.
    needs_picker: bool = False
    # True when the scan screen had a specific activity selected but the
    # scanned player has no subscription for that activity.
    not_enrolled_in_activity: bool = False
    # The name of the activity (if not_enrolled_in_activity is True) so
    # the caller can show a specific message.
    missing_activity_name: str = ""


def _activity_filter_subscriptions(subs: list, activity_id: int) -> list:
    """Return only the subs whose activity_id matches."""
    return [s for s in subs if s.activity_id == activity_id]


def perform_check_in(
    player_id: int,
    parent_widget=None,
    recorded_by: str = None,
    preselect_subscription_id: int = None,
    preselect_activity_id: int = None,
) -> Optional[CheckInOutcome]:
    """
    Full check-in pipeline.

    preselect_subscription_id:
        A specific subscription the caller has already chosen.
    preselect_activity_id:
        A filter — the scan screen is set to a specific activity.
        Only subscriptions for that activity are considered.
        If the player has none, we return not_enrolled_in_activity=True.
    """
    if recorded_by is None:
        recorded_by = _current_recorder()

    player = players_repo.get_by_id(player_id)
    if player is None:
        return None

    # --- Once-per-day guard ---
    if attendance_service.has_checked_in_today(player_id, on_date=date.today()):
        return CheckInOutcome(
            player=player,
            subscription=None,
            checked_in=True,
            reason=None,
            was_override=False,
            was_duplicate=True,
        )

    # --- Get all active subs and optionally filter by activity ---
    all_active = subscription_service.get_all_active(player_id)

    if preselect_activity_id is not None:
        filtered = _activity_filter_subscriptions(all_active, preselect_activity_id)
        if not filtered:
            # Player has no sub in the selected activity. Distinguish this
            # from "no subscription at all" — different UX.
            # Also: maybe they have a sub in that activity that's expired.
            activity_name = ""
            try:
                from services import activity_service
                act = activity_service.get(preselect_activity_id)
                if act:
                    activity_name = activity_service.get_localized_name(act)
            except Exception:
                pass
            return CheckInOutcome(
                player=player,
                subscription=None,
                checked_in=False,
                reason=None,
                was_override=False,
                not_enrolled_in_activity=True,
                missing_activity_name=activity_name,
            )
        active_pool = filtered
    else:
        active_pool = all_active

    # --- If nothing active at all, use the standard validation (which
    #     will produce the right deny reason) ---
    if not active_pool:
        result = validate_check_in(player_id, date.today())
        # Fall through to the deny flow below
    else:
        # We have at least one candidate sub. Build a CheckInResult from
        # the pool directly so we don't rely on validate_check_in's
        # single-sub assumption.
        result = _validate_pool(active_pool, date.today())

    if result.allowed:
        valid = result.valid_subscriptions or [result.subscription]

        # Multiple valid subs + Auto mode → ask the caller to pick
        if len(valid) > 1 and preselect_subscription_id is None:
            return CheckInOutcome(
                player=player,
                subscription=None,
                checked_in=True,
                reason=None,
                was_override=False,
                valid_subscriptions=valid,
                needs_picker=True,
            )

        # Single valid sub OR caller already chose one
        chosen = result.subscription
        if preselect_subscription_id is not None:
            for s in valid:
                if s.subscription_id == preselect_subscription_id:
                    chosen = s
                    break

        sub_id = chosen.subscription_id
        attendance_service.log_attendance(
            player_id, sub_id, "allowed", None, recorded_by
        )
        subscription_service.decrement_session(sub_id)
        chosen.sessions_remaining = max(0, chosen.sessions_remaining - 1)
        return CheckInOutcome(
            player=player,
            subscription=chosen,
            checked_in=True,
            reason=None,
            was_override=False,
            valid_subscriptions=valid,
        )

    # --- Deny flow ---
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
        # Audit — only on actual override
        try:
            from services import audit_service
            audit_service.checkin_override(player_id=player_id, note=note)
        except Exception:
            pass
        return CheckInOutcome(
            player=player,
            subscription=result.subscription,
            checked_in=True,
            reason=None,
            was_override=True,
        )

    attendance_service.log_attendance(
        player_id, sub_id, "denied", result.reason, recorded_by
    )
    return CheckInOutcome(
        player=player,
        subscription=result.subscription,
        checked_in=False,
        reason=result.reason,
        was_override=False,
    )


def _validate_pool(pool: list, today: date):
    """
    Run the validation gates against a specific pool of subscriptions
    (rather than the player's full set). Mirrors logic/validation.py's
    logic but scoped to the pool.
    """
    from dataclasses import dataclass as _dc
    from typing import Optional as _Opt

    @_dc
    class _Result:
        allowed: bool
        reason: _Opt[str]
        subscription: _Opt[Subscription]
        valid_subscriptions: list = field(default_factory=list)

    today_name = today.strftime("%A")
    valid = []
    no_sessions = []
    wrong_day = []

    for sub in pool:
        if sub.sessions_remaining <= 0:
            no_sessions.append(sub)
            continue
        if today_name not in (sub.allowed_days or []):
            wrong_day.append(sub)
            continue
        valid.append(sub)

    if valid:
        return _Result(
            allowed=True, reason=None,
            subscription=valid[0],
            valid_subscriptions=valid,
        )

    if no_sessions and not wrong_day:
        return _Result(
            allowed=False, reason="No sessions remaining",
            subscription=no_sessions[0],
        )

    if wrong_day:
        sub = wrong_day[0]
        days = ", ".join(sub.allowed_days or [])
        return _Result(
            allowed=False,
            reason=f"Not a training day for this plan (allowed: {days})",
            subscription=sub,
        )

    return _Result(
        allowed=False,
        reason="No sessions remaining",
        subscription=no_sessions[0] if no_sessions else pool[0],
    )