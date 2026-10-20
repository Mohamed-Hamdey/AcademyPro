"""
Archive service — soft delete, restore, and permanent delete.

The UI never calls players_repo.archive() directly. Instead, it calls
the methods here, which:

  1. Validate the action (e.g. don't delete the last manager)
  2. Call the repository
  3. Write an audit log entry
  4. Return a result so the UI can update

Permanent delete is destructive and irreversible. It removes the row
AND all related rows (subscriptions, attendance, payments for a player;
attendance for a subscription). Use only from the recycle bin, with
strong confirmation.
"""

import logging
from datetime import date

from repositories import (
    players_repo, subscriptions_repo, attendance_repo, payments_repo,
)
from services import audit_service

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

def archive_player(player_id: int) -> None:
    """
    Move a player to the recycle bin. Their subscription history stays
    intact and the player is restorable.
    """
    player = players_repo.get_by_id(player_id)
    if player is None:
        raise ValueError("Player not found")

    players_repo.archive(player_id)
    log.info("Archived player %s (%s)", player_id, player.full_name)

    audit_service.record(
        "player.archive",
        target_type="player",
        target_id=player_id,
        details={"name": player.full_name},
    )


def restore_player(player_id: int) -> None:
    """Restore a player from the recycle bin."""
    player = players_repo.get_by_id(player_id)
    if player is None:
        raise ValueError("Player not found")

    players_repo.restore(player_id)
    log.info("Restored player %s (%s)", player_id, player.full_name)

    audit_service.record(
        "player.restore",
        target_type="player",
        target_id=player_id,
        details={"name": player.full_name},
    )


def permanently_delete_player(player_id: int) -> None:
    """
    Hard-delete a player and all related rows:
      - subscriptions
      - attendance_log rows
      - payments

    Irreversible. Caller must confirm with the user with typed
    confirmation before calling.

    Audit-log entries referencing this player are preserved (they're
    historical). The player_id will no longer resolve to a player row.
    """
    player = players_repo.get_by_id(player_id)
    if player is None:
        raise ValueError("Player not found")

    if not player.archived_at:
        raise ValueError(
            "Refusing to permanently delete a player that isn't archived"
        )

    name = player.full_name

    from db.database import get_connection
    conn = get_connection()
    try:
        # Order matters — delete children before parents if any FK
        # constraint exists (foreign_keys = ON in get_connection).
        conn.execute(
            "DELETE FROM attendance_log WHERE player_id = ?", (player_id,)
        )
        conn.execute(
            "DELETE FROM payments WHERE player_id = ?", (player_id,)
        )
        conn.execute(
            "DELETE FROM subscriptions WHERE player_id = ?", (player_id,)
        )
        conn.execute(
            "DELETE FROM players WHERE player_id = ?", (player_id,)
        )
        conn.commit()
    finally:
        conn.close()

    log.warning(
        "PERMANENTLY deleted player %s (%s) with all related data",
        player_id, name,
    )

    audit_service.record(
        "player.permanently_delete",
        target_type="player",
        target_id=player_id,
        details={"name": name},
    )


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

def archive_subscription(subscription_id: int) -> None:
    """Move a subscription to the recycle bin."""
    sub = subscriptions_repo.get_by_id(subscription_id)
    if sub is None:
        raise ValueError("Subscription not found")

    subscriptions_repo.archive(subscription_id)
    log.info("Archived subscription %s (player %s)",
             subscription_id, sub.player_id)

    audit_service.record(
        "subscription.archive",
        target_type="subscription",
        target_id=subscription_id,
        details={"player_id": sub.player_id, "activity_id": sub.activity_id},
    )


def restore_subscription(subscription_id: int) -> None:
    """Restore a subscription from the recycle bin."""
    sub = subscriptions_repo.get_by_id(subscription_id)
    if sub is None:
        raise ValueError("Subscription not found")

    subscriptions_repo.restore(subscription_id)
    log.info("Restored subscription %s (player %s)",
             subscription_id, sub.player_id)

    audit_service.record(
        "subscription.restore",
        target_type="subscription",
        target_id=subscription_id,
        details={"player_id": sub.player_id},
    )


def permanently_delete_subscription(subscription_id: int) -> None:
    """
    Hard-delete a subscription and its attendance rows.

    Payments tied to this subscription are PRESERVED (they're a financial
    record — deleting them would lose accounting data). The payment rows
    will have subscription_id set to NULL instead.

    Irreversible. Caller must confirm.
    """
    sub = subscriptions_repo.get_by_id(subscription_id)
    if sub is None:
        raise ValueError("Subscription not found")

    if not sub.archived_at:
        raise ValueError(
            "Refusing to permanently delete a subscription that isn't archived"
        )

    player_id = sub.player_id

    from db.database import get_connection
    conn = get_connection()
    try:
        # Preserve payments but orphan them from the deleted subscription.
        conn.execute(
            "UPDATE payments SET subscription_id = NULL "
            "WHERE subscription_id = ?",
            (subscription_id,),
        )
        # Attendance for this subscription goes away.
        conn.execute(
            "DELETE FROM attendance_log WHERE subscription_id = ?",
            (subscription_id,),
        )
        # Finally, remove the subscription.
        conn.execute(
            "DELETE FROM subscriptions WHERE subscription_id = ?",
            (subscription_id,),
        )
        conn.commit()
    finally:
        conn.close()

    log.warning(
        "PERMANENTLY deleted subscription %s (player %s)",
        subscription_id, player_id,
    )

    audit_service.record(
        "subscription.permanently_delete",
        target_type="subscription",
        target_id=subscription_id,
        details={"player_id": player_id},
    )


# ---------------------------------------------------------------------------
# Recycle bin — bulk operations
# ---------------------------------------------------------------------------

def empty_recycle_bin() -> dict:
    """
    Permanently delete every archived player and archived subscription.

    Returns a summary dict:
        {"players": N, "subscriptions": M}
    """
    archived_players = players_repo.list_archived()
    archived_subs = subscriptions_repo.list_archived()

    for p in archived_players:
        try:
            permanently_delete_player(p.player_id)
        except Exception:
            log.exception("Failed to permanently delete player %s", p.player_id)

    for s in archived_subs:
        try:
            permanently_delete_subscription(s.subscription_id)
        except Exception:
            log.exception(
                "Failed to permanently delete subscription %s",
                s.subscription_id,
            )

    summary = {
        "players": len(archived_players),
        "subscriptions": len(archived_subs),
    }
    log.warning("Recycle bin emptied: %s", summary)
        # Audit: bulk purge
    try:
        from services import audit_service
        audit_service.record(
            "system.empty_recycle_bin",
            details=summary,
        )
    except Exception:
        log.exception("Audit: failed to log empty_recycle_bin")
    return summary


# ---------------------------------------------------------------------------
# Queries for the recycle bin UI
# ---------------------------------------------------------------------------

def get_recycle_bin_contents() -> dict:
    """
    Return what's currently in the recycle bin, for the UI to render.

    Returns:
        {
            "players": [Player, ...],
            "subscriptions": [Subscription, ...],
            "total": N,
        }
    """
    players = players_repo.list_archived()
    subs = subscriptions_repo.list_archived()
    return {
        "players": players,
        "subscriptions": subs,
        "total": len(players) + len(subs),
    }