"""
Championships repository.
"""

from models.championship import Championship, ChampionshipParticipant

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection
# --- Championships ---

def create_championship(champ: Championship) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO championships (name, event_date, activity_id, location, entry_fee, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (champ.name, champ.event_date, champ.activity_id, champ.location, champ.entry_fee, champ.notes)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def update_championship(champ: Championship) -> None:
    conn = get_connection()
    try:
        # Handle the cascading delete (Option B)
        old_champ = get_championship(champ.championship_id)
        if old_champ and old_champ.activity_id != champ.activity_id:
            # Activity changed! Remove players who don't match the new activity
            conn.execute("""
                DELETE FROM championship_players 
                WHERE championship_id = ? 
                AND player_id NOT IN (
                    SELECT player_id FROM subscriptions 
                    WHERE activity_id = ? AND archived_at IS NULL
                )
            """, (champ.championship_id, champ.activity_id))

        conn.execute(
            """
            UPDATE championships 
            SET name = ?, event_date = ?, activity_id = ?, location = ?, entry_fee = ?, notes = ?
            WHERE championship_id = ?
            """,
            (champ.name, champ.event_date, champ.activity_id, champ.location, champ.entry_fee, champ.notes, champ.championship_id)
        )
        conn.commit()
    finally:
        conn.close()

def get_championship(champ_id: int) -> Championship | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM championships WHERE championship_id = ?", (champ_id,)).fetchone()
        return Championship.from_row(row) if row else None
    finally:
        conn.close()

def list_championships(include_archived: bool = False) -> list[Championship]:
    conn = get_connection()
    try:
        where = "" if include_archived else "WHERE archived_at IS NULL"
        rows = conn.execute(f"SELECT * FROM championships {where} ORDER BY event_date DESC").fetchall()
        return [Championship.from_row(r) for r in rows]
    finally:
        conn.close()

def archive_championship(champ_id: int) -> None:
    conn = get_connection()
    try:
        from datetime import datetime
        conn.execute("UPDATE championships SET archived_at = ? WHERE championship_id = ?", (datetime.now().isoformat(), champ_id))
        conn.commit()
    finally:
        conn.close()

def restore_championship(champ_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE championships SET archived_at = NULL WHERE championship_id = ?", (champ_id,))
        conn.commit()
    finally:
        conn.close()

def delete_championship(champ_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM championships WHERE championship_id = ?", (champ_id,))
        conn.commit()
    finally:
        conn.close()

# --- Participants ---

def add_participant(p: ChampionshipParticipant) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO championship_players (championship_id, player_id, weight_kg, belt, result, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (p.championship_id, p.player_id, p.weight_kg, p.belt, p.result, p.notes)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def update_participant(p: ChampionshipParticipant) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE championship_players
            SET weight_kg = ?, belt = ?, result = ?, notes = ?
            WHERE id = ?
            """,
            (p.weight_kg, p.belt, p.result, p.notes, p.id)
        )
        conn.commit()
    finally:
        conn.close()

def remove_participant(participant_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM championship_players WHERE id = ?", (participant_id,))
        conn.commit()
    finally:
        conn.close()

def get_participant(participant_id: int) -> ChampionshipParticipant | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM championship_players WHERE id = ?", (participant_id,)).fetchone()
        return ChampionshipParticipant.from_row(row) if row else None
    finally:
        conn.close()

def list_participants(champ_id: int) -> list[dict]:
    """
    Join with players table to get the player name and ID.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT cp.*, p.full_name 
            FROM championship_players cp
            JOIN players p ON p.player_id = cp.player_id
            WHERE cp.championship_id = ?
            ORDER BY p.full_name COLLATE NOCASE
            """,
            (champ_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
        
        
def get_player_championships(player_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT cp.*, c.name as champ_name, c.event_date, c.location
            FROM championship_players cp
            JOIN championships c ON c.championship_id = cp.championship_id
            WHERE cp.player_id = ?
            ORDER BY c.event_date DESC
            """,
            (player_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()