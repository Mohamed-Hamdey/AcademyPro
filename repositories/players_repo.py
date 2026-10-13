"""
Players repository — all SQL touching the `players` table.
"""

import os
import sys
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection
from models.player import Player


def create(player: Player) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO players
                (full_name, national_id, phone, dob, photo_path,
                 qr_code_path, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                player.full_name, player.national_id, player.phone, player.dob,
                player.photo_path, player.qr_code_path,
                player.status, player.notes,
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
            "SELECT * FROM players ORDER BY full_name COLLATE NOCASE"
        ).fetchall()
        return [Player.from_row(r) for r in rows]
    finally:
        conn.close()


def search_by_name(name_fragment: str) -> list[Player]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM players WHERE full_name LIKE ?",
            (f"%{name_fragment}%",),
        ).fetchall()
        return [Player.from_row(r) for r in rows]
    finally:
        conn.close()


def update(player: Player) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE players
            SET full_name = ?, national_id = ?, phone = ?, dob = ?,
                photo_path = ?, qr_code_path = ?, status = ?, notes = ?
            WHERE player_id = ?
            """,
            (
                player.full_name, player.national_id, player.phone, player.dob,
                player.photo_path, player.qr_code_path,
                player.status, player.notes, player.player_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()