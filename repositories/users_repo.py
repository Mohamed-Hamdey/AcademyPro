"""
Users repository — all SQL touching the `users` table.
"""

import os
import sys
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db.database import get_connection


@dataclass
class User:
    user_id: Optional[int]
    username: str
    display_name: str
    password_hash: str
    role: str                      # "manager" | "receptionist"
    active: bool = True
    photo_path: Optional[str] = None
    last_login: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "User":
        # photo_path may be missing on very old DBs — use .keys() to check.
        keys = row.keys() if hasattr(row, "keys") else []
        return cls(
            user_id=row["user_id"],
            username=row["username"],
            display_name=row["display_name"],
            password_hash=row["password_hash"],
            role=row["role"],
            active=bool(row["active"]),
            photo_path=row["photo_path"] if "photo_path" in keys else None,
            last_login=row["last_login"],
            created_at=row["created_at"],
        )


def create(username: str, display_name: str, password_hash: str, role: str,
           photo_path: Optional[str] = None) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO users (username, display_name, password_hash, role, photo_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, display_name, password_hash, role, photo_path),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_by_id(user_id: int) -> Optional[User]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return User.from_row(row) if row else None
    finally:
        conn.close()


def get_by_username(username: str) -> Optional[User]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return User.from_row(row) if row else None
    finally:
        conn.close()


def list_all() -> list[User]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY role DESC, username"
        ).fetchall()
        return [User.from_row(r) for r in rows]
    finally:
        conn.close()


def search(query: str) -> list[User]:
    """
    Search users by username or display name. Used by the users screen
    search bar. An empty query returns everything.
    """
    if not query:
        return list_all()
    conn = get_connection()
    try:
        like = f"%{query}%"
        rows = conn.execute(
            """
            SELECT * FROM users
            WHERE username LIKE ? OR display_name LIKE ?
            ORDER BY role DESC, username
            """,
            (like, like),
        ).fetchall()
        return [User.from_row(r) for r in rows]
    finally:
        conn.close()


def update(user: User) -> None:
    """
    Update display_name, role, active, photo_path. Username and password
    are intentionally not updated here — those go through dedicated
    functions so it's clear when they change.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE users
            SET display_name = ?, role = ?, active = ?, photo_path = ?
            WHERE user_id = ?
            """,
            (user.display_name, user.role, int(user.active),
             user.photo_path, user.user_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_password(user_id: int, password_hash: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE user_id = ?",
            (password_hash, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_active(user_id: int, active: bool) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET active = ? WHERE user_id = ?",
            (int(active), user_id),
        )
        conn.commit()
    finally:
        conn.close()


def touch_last_login(user_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET last_login = datetime('now') WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def count_active_managers() -> int:
    """How many active managers exist. Used to prevent locking everyone out."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'manager' AND active = 1"
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()