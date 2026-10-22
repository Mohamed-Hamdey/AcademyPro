"""
Players repository — all SQL touching the `players` table.
"""

import os
import sys
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection
from models.player import Player
from logic.arabic_normalize import normalize_arabic


def create(player: Player) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO players
                (full_name, national_id, phone, dob, photo_path,
                 qr_code_path, status, notes, belt, weight_kg, session_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                player.full_name, player.national_id, player.phone, player.dob,
                player.photo_path, player.qr_code_path,
                player.status, player.notes,
                player.belt, player.weight_kg, player.session_time, # <--- NEW
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_by_id(player_id: int) -> Optional[Player]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM players WHERE player_id = ?", (player_id,)
        ).fetchone()
        return Player.from_row(row) if row else None
    finally:
        conn.close()


def get_by_national_id(national_id: str) -> Optional[Player]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM players WHERE national_id = ?", (national_id,)
        ).fetchone()
        return Player.from_row(row) if row else None
    finally:
        conn.close()


def list_all() -> list[Player]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM players "
            "WHERE archived_at IS NULL "
            "ORDER BY full_name COLLATE NOCASE"
        ).fetchall()
        return [Player.from_row(r) for r in rows]
    finally:
        conn.close()


def search_by_name(name_fragment: str) -> list[Player]:
    """
    Search players by name (with Arabic normalization) or by numeric ID.

    - If the query is purely numeric, also matches player_id.
    - Arabic text is normalized before comparison, so "احمد" matches
      "أحمد" and "فاطمه" matches "فاطمة".

    Returns the matching players, newest first by ID as a tiebreaker.
    """
    query = (name_fragment or "").strip()
    if not query:
        return list_all()

    normalized_query = normalize_arabic(query).lower()
    like_clause = f"%{normalized_query}%"
    raw_like = f"%{query.lower()}%"

    conn = get_connection()
    try:
        # Two-pronged match:
        #   1. Raw LIKE against full_name (works for Latin and exact Arabic)
        #   2. Numeric match against player_id (for ID search)
        #
        # Then post-filter the raw matches by applying normalize_arabic
        # to each player's full_name in Python, since SQLite doesn't
        # ship with a normalization function.
        if query.isdigit():
            where = (
                "archived_at IS NULL AND "
                "(LOWER(full_name) LIKE ? OR player_id = ?)"
            )
            params = [raw_like, int(query)]
        else:
            where = "archived_at IS NULL AND LOWER(full_name) LIKE ?"
            params = [raw_like]
        rows = conn.execute(
            f"SELECT * FROM players WHERE {where} ORDER BY player_id DESC",
            params,
        ).fetchall()

        candidates = [Player.from_row(r) for r in rows]

        # Now augment with any player whose NORMALIZED name matches but
        # whose raw name didn't (e.g. query "احمد" vs stored "أحمد").
        if normalized_query:
            extra = conn.execute(
                "SELECT * FROM players "
                "WHERE archived_at IS NULL "
                "ORDER BY player_id DESC"
            ).fetchall()
            already = {p.player_id for p in candidates}
            for r in extra:
                p = Player.from_row(r)
                if p.player_id in already:
                    continue
                normalized_name = normalize_arabic(p.full_name or "").lower()
                if normalized_query in normalized_name:
                    candidates.append(p)

        return candidates
    finally:
        conn.close()


def list_archived() -> list[Player]:
    """All players that have been soft-deleted."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM players "
            "WHERE archived_at IS NOT NULL "
            "ORDER BY archived_at DESC"
        ).fetchall()
        return [Player.from_row(r) for r in rows]
    finally:
        conn.close()


def archive(player_id: int) -> None:
    """Soft-delete: stamp archived_at with the current timestamp."""
    from datetime import datetime
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE players SET archived_at = ? WHERE player_id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), player_id),
        )
        conn.commit()
    finally:
        conn.close()


def restore(player_id: int) -> None:
    """Un-archive: clear archived_at."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE players SET archived_at = NULL WHERE player_id = ?",
            (player_id,),
        )
        conn.commit()
    finally:
        conn.close()

def update(player: Player) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE players
            SET full_name = ?, national_id = ?, phone = ?, dob = ?,
                photo_path = ?, qr_code_path = ?, status = ?, notes = ?,
                belt = ?, weight_kg = ?, session_time = ?
            WHERE player_id = ?
            """,
            (
                player.full_name, player.national_id, player.phone, player.dob,
                player.photo_path, player.qr_code_path,
                player.status, player.notes,
                player.belt, player.weight_kg, player.session_time, # <--- NEW
                player.player_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
        
# ---------------------------------------------------------------------------
# List / search with details (for the redesigned player list screen)
# ---------------------------------------------------------------------------
#
# These methods return one dict per row, with everything the table
# needs to render without N+1 queries. The dict has this shape:
#
#   {
#       "player": Player,                    # the Player dataclass
#       "subscriptions": [Subscription, ...],# all active subs for the row
#       "status": "active" | "expired" | "suspended" | "none",
#       "activity_names": [str, ...],        # localized, for pill rendering
#       "activity_ids": [int, ...],
#       "plan_label": str,                   # for the Plan column
#       "sessions_remaining": int | None,
#       "sessions_total": int | None,
#       "expiry_date": str | None,           # ISO date
#       "days_left": int | None,             # days until expiry (negative = past)
#   }
#
# The service layer wraps these and adds filters (activity, status, search).
# ---------------------------------------------------------------------------

def _build_detail_dict(player, subscriptions):
    """
    Compose the per-row dict the UI needs, from a Player and their
    active subscriptions (as Subscription objects).

    Handles the edge cases:
      - 0 subs: status="none", plan/sessions/expiry None
      - 1+ subs: aggregate for the "All" view (uses the earliest-expiring
        active sub for the Plan/Sessions/Expires columns, so the row
        highlights the most-urgent one)
    """
    from datetime import date as _date

    today = _date.today()

    if not subscriptions:
        return {
            "player": player,
            "subscriptions": [],
            "status": "none",
            "activity_names": [],
            "activity_ids": [],
            "plan_label": "",
            "sessions_remaining": None,
            "sessions_total": None,
            "expiry_date": None,
            "days_left": None,
        }

    # Sort by expiry ascending so the most-urgent sub is first.
    subs_sorted = sorted(subscriptions, key=lambda s: s.expiry_date)

    most_urgent = subs_sorted[0]

    try:
        expiry = _date.fromisoformat(most_urgent.expiry_date)
        days_left = (expiry - today).days
    except Exception:
        days_left = None

    # Aggregate activity names for pill rendering.
    from services import activity_service
    activity_ids = []
    activity_names = []
    for s in subs_sorted:
        if s.activity_id is None:
            continue
        if s.activity_id in activity_ids:
            continue
        activity_ids.append(s.activity_id)
        act = activity_service.get(s.activity_id)
        if act:
            activity_names.append(activity_service.get_localized_name(act))

    return {
        "player": player,
        "subscriptions": subs_sorted,
        "status": "active",
        "activity_names": activity_names,
        "activity_ids": activity_ids,
        "plan_label": str(most_urgent.plan_type).strip() if most_urgent.plan_type is not None else "",
        "sessions_remaining": most_urgent.sessions_remaining,
        "sessions_total": most_urgent.sessions_total,
        "expiry_date": most_urgent.expiry_date,
        "days_left": days_left,
    }


def list_with_details() -> list[dict]:
    """
    All non-archived players with their active subscription summary.
    One row per player. Players with 0 active subs still appear (status="none").
    """
    # 1. Fetch all players (one query).
    players = list_all()

    if not players:
        return []

    # 2. Fetch all active subscriptions in one batch query.
    from repositories.subscriptions_repo import get_all_active_for_players
    player_ids = [p.player_id for p in players]
    subs_by_player = get_all_active_for_players(player_ids)

    # 3. Build the detail dicts.
    return [
        _build_detail_dict(p, subs_by_player.get(p.player_id, []))
        for p in players
    ]


def list_with_details_for_activity(activity_id: int) -> list[dict]:
    """
    Non-archived players who have at least one active subscription in
    the given activity.
    """
    from repositories.subscriptions_repo import get_all_active_for_players

    players = list_all()
    if not players:
        return []

    player_ids = [p.player_id for p in players]
    subs_by_player = get_all_active_for_players(player_ids)

    result = []
    for p in players:
        all_subs = subs_by_player.get(p.player_id, [])
        activity_subs = [s for s in all_subs if s.activity_id == activity_id]
        if not activity_subs:
            continue
        # For activity tabs, show only the activity's subscription(s),
        # not all of the player's subs.
        result.append(_build_detail_dict(p, activity_subs))
    return result


def search_with_details(query: str) -> list[dict]:
    """
    Search for players by name/ID, returning the same row shape as
    list_with_details().
    """
    if not query or not query.strip():
        return list_with_details()

    # Reuse the existing search logic to find matching players.
    matching = search_by_name(query)
    if not matching:
        return []

    from repositories.subscriptions_repo import get_all_active_for_players
    player_ids = [p.player_id for p in matching]
    subs_by_player = get_all_active_for_players(player_ids)

    return [
        _build_detail_dict(p, subs_by_player.get(p.player_id, []))
        for p in matching
    ]


def search_with_details_for_activity(activity_id: int, query: str) -> list[dict]:
    """Search within a specific activity tab."""
    if not query or not query.strip():
        return list_with_details_for_activity(activity_id)

    matching = search_by_name(query)
    if not matching:
        return []

    from repositories.subscriptions_repo import get_all_active_for_players
    player_ids = [p.player_id for p in matching]
    subs_by_player = get_all_active_for_players(player_ids)

    result = []
    for p in matching:
        all_subs = subs_by_player.get(p.player_id, [])
        activity_subs = [s for s in all_subs if s.activity_id == activity_id]
        if not activity_subs:
            continue
        result.append(_build_detail_dict(p, activity_subs))
    return result


# ---------------------------------------------------------------------------
# Summary counts
# ---------------------------------------------------------------------------

def count_by_status() -> dict:
    """
    Return counts for the summary strip:
        {
            "active": N,        # players with >=1 active sub
            "expired": N,       # players with 0 active, but their most-recent sub is expired
            "suspended": N,     # same, but suspended
            "none": N,          # players who have never had a subscription
            "expiring_soon": N, # active players whose earliest expiry is <= 7 days
            "low_sessions": N,  # active players with a sub <= 1 sessions remaining
        }

    All counts are unique players.
    """
    from datetime import date as _date

    players = list_all()
    if not players:
        return {
            "active": 0, "expired": 0, "suspended": 0, "none": 0,
            "expiring_soon": 0, "low_sessions": 0,
        }

    from repositories.subscriptions_repo import get_all_active_for_players
    from repositories.subscriptions_repo import get_history_for_player as _hist

    player_ids = [p.player_id for p in players]
    subs_by_player = get_all_active_for_players(player_ids)

    today = _date.today()
    counts = {
        "active": 0, "expired": 0, "suspended": 0, "none": 0,
        "expiring_soon": 0, "low_sessions": 0,
    }

    for p in players:
        subs = subs_by_player.get(p.player_id, [])
        if subs:
            counts["active"] += 1
            try:
                earliest = min(_date.fromisoformat(s.expiry_date) for s in subs)
                if (earliest - today).days <= 7:
                    counts["expiring_soon"] += 1
            except Exception:
                pass
            if any(s.sessions_remaining <= 1 for s in subs):
                counts["low_sessions"] += 1
        else:
            hist = _hist(p.player_id)
            if not hist:
                counts["none"] += 1
            else:
                latest = hist[0]
                # Check if it's recently expired (e.g., within the last 30 days)
                try:
                    exp_date = _date.fromisoformat(latest.expiry_date)
                    recently = (today - exp_date).days <= 30
                except:
                    recently = True

                if latest.status == "expired" and recently:
                    counts["expired"] += 1
                elif latest.status == "suspended":
                    counts["suspended"] += 1
                else:
                    counts["none"] += 1

    return counts


def count_by_status_for_activity(activity_id: int) -> dict:
    """
    Same shape as count_by_status(), but only for players with at
    least one subscription (active or historical) in the given activity.
    """
    from datetime import date as _date
    from db.database import get_connection

    conn = get_connection()
    try:
        # Players who have ever touched this activity.
        rows = conn.execute(
            "SELECT DISTINCT player_id FROM subscriptions WHERE activity_id = ?",
            (activity_id,),
        ).fetchall()
        player_ids = [r[0] for r in rows]
    finally:
        conn.close()

    if not player_ids:
        return {
            "active": 0, "expired": 0, "suspended": 0, "none": 0,
            "expiring_soon": 0, "low_sessions": 0,
        }

    from repositories.subscriptions_repo import get_all_active_for_players
    subs_by_player = get_all_active_for_players(player_ids)

    today = _date.today()
    counts = {
        "active": 0, "expired": 0, "suspended": 0, "none": 0,
        "expiring_soon": 0, "low_sessions": 0,
    }

    for pid in player_ids:
        subs = [s for s in subs_by_player.get(pid, [])
                if s.activity_id == activity_id]
        if subs:
            counts["active"] += 1
            try:
                earliest = min(_date.fromisoformat(s.expiry_date) for s in subs)
                if (earliest - today).days <= 7:
                    counts["expiring_soon"] += 1
            except Exception:
                pass
            if any(s.sessions_remaining <= 1 for s in subs):
                counts["low_sessions"] += 1
        # For non-active in this activity, we don't try to compute
        # expired/suspended precisely — this is a summary strip, precision
        # is fine to lose. Players with no active sub in the activity
        # are excluded from the count entirely.

    return counts


def list_activity_counts() -> dict[int, int]:
    """
    Return {activity_id: player_count} — number of non-archived players
    with at least one active subscription in each activity.

    Used to render the tab bar counts.
    """
    from db.database import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT s.activity_id,
                   COUNT(DISTINCT s.player_id) AS cnt
            FROM subscriptions s
            JOIN players p ON p.player_id = s.player_id
            WHERE s.status = 'active'
              AND s.archived_at IS NULL
              AND p.archived_at IS NULL
            GROUP BY s.activity_id
            """,
        ).fetchall()
        return {r["activity_id"]: r["cnt"] for r in rows}
    finally:
        conn.close()
        
        
# ---------------------------------------------------------------------------
# Player Measurements
# ---------------------------------------------------------------------------

def add_measurement(player_id: int, recorded_at: str, weight_kg: float, belt: str, notes: str = None) -> int:
    """Record a new measurement in history."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO player_measurements (player_id, recorded_at, weight_kg, belt, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (player_id, recorded_at, weight_kg, belt, notes),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def get_measurements(player_id: int) -> list[dict]:
    """Fetch all measurements for a player, ordered oldest to newest."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM player_measurements WHERE player_id = ? ORDER BY recorded_at ASC",
            (player_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
        
def count_active() -> int:
    """Fast count of non-archived players. One query, no joins."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM players WHERE archived_at IS NULL"
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()