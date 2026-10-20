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
from typing import Optional

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



# ---------------------------------------------------------------------------
# Additions for the audit-screen rebuild (D1, 2026-04).
#
# These are the plumbing for the screen's footer, the Clear button, and
# the rolling-retention hook called from main.py on startup. They do not
# touch the existing record()/convenience wrappers above.
# ---------------------------------------------------------------------------

import logging  # already imported at top, but re-importing is safe and
                # keeps this block self-contained if someone reorders.

# Actions whose prefix marks them as "attendance noise" that must be
# hidden from the audit screen (Q3=A). They still get written (so the
# DB retains the history if ever needed) but the UI filters them out.
_HIDDEN_FROM_SCREEN_PREFIXES = ("attendance.",)


def _is_hidden_from_screen(action: str) -> bool:
    """True if this action is written to the DB but hidden from the UI."""
    return any(action.startswith(p) for p in _HIDDEN_FROM_SCREEN_PREFIXES)


def query_ui(
    search: str = "",
    action: Optional[str] = None,
    username: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 1000,
) -> dict:
    """
    Wrapper around audit_repo.query() used by the Audit Screen.

    Differences vs the raw repo call:
      * Filters out hidden actions (attendance.*) per Q3=A.
      * Returns a dict with both the rows AND the total count so the
        footer can show "Showing X of Y rows".

    Return shape:
        {
            "rows":  [AuditEntry, ...],       # up to `limit` entries
            "shown": int,                     # len(rows)
            "total": int,                     # count matching filter
            "oldest": str | None,             # global MIN(created_at)
        }

    Note: `oldest` is the GLOBAL oldest row in the whole table, not the
    oldest within the filter. That's intentional — the footer tells the
    user "retention covers this far back" regardless of what they've
    filtered to.
    """
    rows = audit_repo.query(
        search=search,
        action=action,
        username=username,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    # Hide attendance.* from the screen (Q3=A).
    visible = [r for r in rows if not _is_hidden_from_screen(r.action)]

    total = audit_repo.count_matching(
        search=search,
        action=action,
        username=username,
        date_from=date_from,
        date_to=date_to,
    )
    # count_matching counts EVERYTHING, including the hidden actions.
    # For the footer, we want the count of what the user *could* see
    # after filtering. So subtract the hidden ones. Because hidden
    # actions are only `attendance.*`, and the count filter is
    # generic, the simplest correct approach is to count the hidden
    # rows explicitly and subtract them.
    if _HIDDEN_FROM_SCREEN_PREFIXES:
        hidden_count = _count_hidden_matching(
            search=search,
            action=action,
            username=username,
            date_from=date_from,
            date_to=date_to,
        )
        total = max(0, total - hidden_count)

    return {
        "rows": visible,
        "shown": len(visible),
        "total": total,
        "oldest": audit_repo.oldest_created_at(),
    }


def _count_hidden_matching(
    search: str = "",
    action: Optional[str] = None,
    username: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> int:
    """
    Count rows matching the filter that ALSO match a hidden prefix.
    Only called from query_ui() to subtract hidden actions from the total.

    If `action` is set and it isn't a hidden prefix, this returns 0 —
    the caller's filter already excludes hidden actions.
    """
    # If the caller filtered by an action, and it's not hidden, no subtraction needed.
    if action and not _is_hidden_from_screen(action):
        return 0

    total_hidden = 0
    for prefix in _HIDDEN_FROM_SCREEN_PREFIXES:
        # Reuse the repo's count but with a LIKE on the action prefix.
        # audit_repo.count_matching() only supports exact `action =`,
        # so we do it here with a small dedicated query.
        from db.database import get_connection
        conn = get_connection()
        try:
            clauses = ["action LIKE ?"]
            params: list = [f"{prefix}%"]

            if search:
                like = f"%{search}%"
                clauses.append(
                    "(username LIKE ? OR action LIKE ? OR target_type LIKE ?)"
                )
                params.extend([like, like, like])

            if username:
                clauses.append("username = ?")
                params.append(username)

            if date_from:
                clauses.append("substr(created_at, 1, 10) >= ?")
                params.append(date_from)

            if date_to:
                clauses.append("substr(created_at, 1, 10) <= ?")
                params.append(date_to)

            where = "WHERE " + " AND ".join(clauses)
            row = conn.execute(
                f"SELECT COUNT(*) FROM audit_log {where}",
                params,
            ).fetchone()
            total_hidden += int(row[0]) if row else 0
        finally:
            conn.close()
    return total_hidden


def clear(reason: Optional[str] = None) -> dict:
    """
    Wipe the audit log, then write ONE audit.clear row recording who
    did it, when, and (optionally) why (R6 — the clear is itself
    audited).

    Return shape:
        {"deleted": int, "kept": 1}
    """
    deleted = audit_repo.delete_all()
    # Record the clear action AFTER deleting — this row survives.
    # If delete_all() raised, we never reach this line and the log is
    # intact — safe by construction.
    record(
        "audit.clear",
        target_type="audit_log",
        target_id=None,
        details={"rows_deleted": deleted, "reason": reason},
    )
    logging.getLogger(__name__).warning(
        "Audit log cleared by %s: %d rows removed",
        app_state.recorded_by(),
        deleted,
    )
    return {"deleted": deleted, "kept": 1}


def purge_older_than(days: int = 30) -> dict:
    """
    Rolling retention — delete every row older than `days` days.

    Called once per app start from main.py. If `days <= 0`, this is a
    no-op (never purge everything by accident).

    Return shape:
        {"deleted": int, "cutoff": "YYYY-MM-DD HH:MM:SS", "days": int}
    """
    from datetime import datetime, timedelta

    if days is None or days <= 0:
        return {"deleted": 0, "cutoff": None, "days": days}

    cutoff = (datetime.now() - timedelta(days=days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    deleted = audit_repo.delete_before(cutoff)
    if deleted:
        logging.getLogger(__name__).info(
            "Purged %d audit rows older than %d days (cutoff %s)",
            deleted, days, cutoff,
        )
    return {"deleted": deleted, "cutoff": cutoff, "days": days}