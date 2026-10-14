"""
Player history service.

Merges two sources into a single chronological timeline:
  * attendance_log — every scan (allowed / denied / override)
  * audit_log      — every admin action that touched this player or one
                     of their subscriptions

The result is a list of TimelineEvent objects sorted newest-first.
"""

import os
import sys
from dataclasses import dataclass
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection
from repositories import subscriptions_repo


# ---------------------------------------------------------------------------
# Timeline event
# ---------------------------------------------------------------------------

@dataclass
class TimelineEvent:
    when: str                # ISO-ish datetime string "YYYY-MM-DD HH:MM:SS"
    kind: str                # "attendance" | "subscription" | "payment" | "player"
    action: str              # e.g. "allowed", "denied", "subscription.activate"
    summary: str             # human-readable, localized
    details: dict            # extra structured data (amounts, days, etc.)


# ---------------------------------------------------------------------------
# Query + merge
# ---------------------------------------------------------------------------

def get_timeline(player_id: int) -> list[TimelineEvent]:
    events = []
    events.extend(_attendance_events(player_id))
    events.extend(_payment_events(player_id))
    events.extend(_audit_events(player_id))
    events.sort(key=lambda e: e.when, reverse=True)
    return events


def _attendance_events(player_id: int) -> list[TimelineEvent]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT a.*, p.full_name
            FROM attendance_log a
            LEFT JOIN players p ON p.player_id = a.player_id
            WHERE a.player_id = ?
            ORDER BY a.scan_datetime DESC
            """,
            (player_id,),
        ).fetchall()
    finally:
        conn.close()

    events = []
    for r in rows:
        action = r["result"]
        if r["was_override"]:
            action += "_override"
        summary = _attendance_summary(action, r)
        events.append(TimelineEvent(
            when=r["scan_datetime"],
            kind="attendance",
            action=action,
            summary=summary,
            details={
                "result": r["result"],
                "was_override": bool(r["was_override"]),
                "override_note": r["override_note"],
                "deny_reason": r["deny_reason"],
                "recorded_by": r["recorded_by"],
                "subscription_id": r["subscription_id"],
                "activity_id": r["activity_id"],
            },
        ))
    return events

def _payment_events(player_id: int) -> list[TimelineEvent]:
    """
    Every payment for this player, sourced from the payments ledger.
    """
    from repositories import payments_repo
    from ui.i18n import t

    payments = payments_repo.list_for_player(player_id)
    events = []
    for p in payments:
        sign = "−" if p.amount < 0 else ""
        amount = f"{sign}{abs(p.amount):,.0f} {p.currency}"
        summary = t("history.payment.recorded", amount=amount, method=p.method)
        if p.notes:
            summary += f" · {p.notes}"
        events.append(TimelineEvent(
            when=f"{p.payment_date} 00:00:00",
            kind="payment",
            action="payment.recorded",
            summary=summary,
            details={
                "amount": p.amount,
                "currency": p.currency,
                "method": p.method,
                "notes": p.notes,
                "recorded_by": p.recorded_by,
                "subscription_id": p.subscription_id,
            },
        ))
    return events

def _attendance_summary(action: str, row) -> str:
    """Localized short text like 'Allowed · Kung Fu' or 'Denied (no sessions)'."""
    from ui.i18n import t
    from services import activity_service

    # Try to resolve the activity name
    act_name = ""
    if row["activity_id"]:
        try:
            act = activity_service.get(row["activity_id"])
            if act:
                act_name = activity_service.get_localized_name(act)
        except Exception:
            pass

    if row["result"] == "allowed":
        if row["was_override"]:
            base = t("history.attendance.allowed_override")
        else:
            base = t("history.attendance.allowed")
    else:
        base = t("history.attendance.denied")
        if row["deny_reason"]:
            base += f" — {row['deny_reason']}"

    if act_name:
        return f"{base} · {act_name}"
    return base


def _audit_events(player_id: int) -> list[TimelineEvent]:
    """
    Pull audit rows that target this player OR one of their subscriptions.
    """
    # First: all subscription IDs for this player
    history = subscriptions_repo.get_history_for_player(player_id)
    sub_ids = [s.subscription_id for s in history if s.subscription_id is not None]

    conn = get_connection()
    try:
        # Player-targeted rows
        query_player = """
            SELECT * FROM audit_log
            WHERE target_type = 'player' AND target_id = ?
        """
        player_rows = conn.execute(query_player, (player_id,)).fetchall()

        # Subscription-targeted rows
        sub_rows = []
        if sub_ids:
            placeholders = ",".join("?" for _ in sub_ids)
            query_subs = f"""
                SELECT * FROM audit_log
                WHERE target_type = 'subscription' AND target_id IN ({placeholders})
            """
            sub_rows = conn.execute(query_subs, sub_ids).fetchall()
    finally:
        conn.close()

    events = []
    for r in list(player_rows) + list(sub_rows):
        action = r["action"]
        # Skip payment audits — the payments ledger now provides these
        # with the actual amount, so showing both would be a duplicate.
        if action == "subscription.record_payment":
            continue
        events.append(TimelineEvent(
            when=r["created_at"],
            kind=_audit_kind(action),
            action=action,
            summary=_audit_summary(action, r, player_id, sub_ids),
            details={
                "details": r["details"],
                "username": r["username"],
                "target_type": r["target_type"],
                "target_id": r["target_id"],
            },
        ))
    return events


def _audit_kind(action: str) -> str:
    if action.startswith("subscription.record_payment"):
        return "payment"
    if action.startswith("subscription."):
        return "subscription"
    if action.startswith("attendance."):
        return "attendance"
    if action.startswith("player."):
        return "player"
    return "admin"


def _audit_summary(action: str, row, player_id: int, sub_ids: list) -> str:
    """Localized summary for an audit row."""
    from ui.i18n import t
    from services import activity_service

    # Resolve the activity name if this row targets a subscription
    act_name = ""
    if row["target_type"] == "subscription" and row["target_id"] in sub_ids:
        try:
            sub = subscriptions_repo.get_by_id(row["target_id"])
            if sub and sub.activity_id:
                act = activity_service.get(sub.activity_id)
                if act:
                    act_name = activity_service.get_localized_name(act)
        except Exception:
            pass

    # Map action → localized label
    label_key = f"audit.action.{action}"
    label = t(label_key)
    if label == label_key:
        label = action  # fallback to code

    if act_name:
        return f"{label} · {act_name}"
    return label


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def timeline_to_csv_rows(events: list[TimelineEvent]) -> list[list[str]]:
    """
    Convert a timeline to rows suitable for CSV export.
    Columns: Timestamp, Type, Action, Summary, Recorded By
    """
    rows = [["Timestamp", "Type", "Action", "Summary", "Recorded By"]]
    for e in events:
        recorded_by = e.details.get("recorded_by") or e.details.get("username") or ""
        rows.append([e.when, e.kind, e.action, e.summary, recorded_by])
    return rows