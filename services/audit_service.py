"""
Audit service — records admin actions with the current user attached.

Every call goes through `record(...)`, which auto-fills the current user
from `app_state`. Callers just specify the action and target.

Usage:
    from services import audit_service
    audit_service.record(
        "subscription.suspend",
        target_type="subscription", target_id=sub_id,
        details={"reason": "requested by parent"},
    )
"""

import os
import sys
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from repositories import audit_repo
from app_state import app as app_state


def record(action: str,
           target_type: str = None,
           target_id: int = None,
           details: dict = None,
           username: str = None) -> int:
    """
    Write one audit entry for the currently logged-in user.

    `username` is an optional override — used by pre-auth events
    (e.g. failed login attempts) where there is no authenticated user
    but we still know which username was attempted. When the override
    is set, `user_id` is recorded as None.

    Called from anywhere; never raises on failure — an audit write
    failing should not break the underlying action.
    """
    try:
        if username is None:
            user = app_state.user
            user_id = user.user_id if user else None
            username = user.username if user else "system"
        else:
            # Explicit override — pre-auth event, no authenticated user.
            user_id = None

        return audit_repo.write(
            user_id=user_id,
            username=username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
    except Exception:
        # Logging must never break the action. Record and move on.

        logging.getLogger(__name__).exception(
            "Failed to record audit action %s", action
        )
        return -1

# -------- convenience wrappers for common actions --------

def user_created(user_id: int, username: str):
    record("user.create", target_type="user", target_id=user_id,
           details={"username": username})

def user_updated(user_id: int, username: str, changes: dict):
    record("user.update", target_type="user", target_id=user_id,
           details={"username": username, "changes": changes})

def user_password_changed(user_id: int, username: str, by_admin: bool):
    record("user.password_change", target_type="user", target_id=user_id,
           details={"username": username, "by_admin": by_admin})

def player_created(player_id: int, name: str):
    record("player.create", target_type="player", target_id=player_id,
           details={"name": name})

def player_updated(player_id: int, name: str):
    record("player.update", target_type="player", target_id=player_id,
           details={"name": name})

def qr_reissued(player_id: int, name: str):
    record("player.qr_reissue", target_type="player", target_id=player_id,
           details={"name": name})

def subscription_activated(subscription_id: int, player_id: int, plan: str):
    record("subscription.activate", target_type="subscription",
           target_id=subscription_id,
           details={"player_id": player_id, "plan_type": plan})

def subscription_suspended(subscription_id: int):
    record("subscription.suspend", target_type="subscription",
           target_id=subscription_id)

def subscription_sessions_adjusted(subscription_id: int,
                                   old_value: int, new_value: int):
    record("subscription.adjust_sessions", target_type="subscription",
           target_id=subscription_id,
           details={"old": old_value, "new": new_value})

def payment_recorded(subscription_id: int, amount: float, payment_date: str):
    record("subscription.record_payment", target_type="subscription",
           target_id=subscription_id,
           details={"amount": amount, "date": payment_date})

def attendance_undone(log_id: int, player_id: int):
    record("attendance.undo", target_type="attendance", target_id=log_id,
           details={"player_id": player_id})

def manual_checkin(player_id: int):
    record("attendance.manual_checkin", target_type="player",
           target_id=player_id)

def checkin_override(player_id: int, note: str):
    record("attendance.override", target_type="player", target_id=player_id,
           details={"note": note})
    
# -------- auth events --------
# These two are called from the login screen. `auth.login` fires AFTER
# app_state has been populated, so it records as the real user.
# `auth.login_failed` fires BEFORE app_state is set (or with no user),
# so it lands with username="system" and user_id=None — which is exactly
# what we want for an unsuccessful attempt.

def auth_login(username: str):
    record("auth.login", target_type="user",
           details={"username": username})

def auth_login_failed(attempted_username: str, reason: str = "bad_credentials"):
    record(
        "auth.login_failed",
        # The username column shows WHO the attempt was for, which is
        # more useful at a glance than "system". user_id stays None
        # because no one was actually authenticated.
        username=attempted_username,
        details={"reason": reason},
    )

def auth_logout(username: str):
    record("auth.logout", details={"username": username})