"""
Temporary test script for the archive filter.
Run once, verify the app behavior, then delete.

Usage:
    python test_archive.py archive 1        → archives player 1
    python test_archive.py restore 1        → restores player 1
    python test_archive.py list             → shows archived players
    python test_archive.py archive_sub 1    → archives subscription 1
    python test_archive.py restore_sub 1    → restores subscription 1
    python test_archive.py list_subs        → shows archived subscriptions
"""

import sqlite3
import sys
from datetime import datetime


DB_PATH = r"C:\Users\PC\AppData\Local\AcademySystem\academy.db"


def archive_player(player_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE players SET archived_at = ? WHERE player_id = ?",
            (now, player_id),
        )
        conn.commit()
        print(f"Archived player {player_id} at {now}")
    finally:
        conn.close()


def restore_player(player_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE players SET archived_at = NULL WHERE player_id = ?",
            (player_id,),
        )
        conn.commit()
        print(f"Restored player {player_id}")
    finally:
        conn.close()


def list_archived_players():
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT player_id, full_name, archived_at FROM players "
            "WHERE archived_at IS NOT NULL ORDER BY archived_at DESC"
        ).fetchall()
        if not rows:
            print("No archived players.")
            return
        print(f"{'ID':<6} {'Archived at':<20} {'Name'}")
        print("-" * 60)
        for pid, name, at in rows:
            print(f"{pid:<6} {at:<20} {name}")
    finally:
        conn.close()


def archive_subscription(sub_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE subscriptions SET archived_at = ? WHERE subscription_id = ?",
            (now, sub_id),
        )
        conn.commit()
        print(f"Archived subscription {sub_id} at {now}")
    finally:
        conn.close()


def restore_subscription(sub_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE subscriptions SET archived_at = NULL WHERE subscription_id = ?",
            (sub_id,),
        )
        conn.commit()
        print(f"Restored subscription {sub_id}")
    finally:
        conn.close()


def list_archived_subs():
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT s.subscription_id, pl.full_name, s.activity_id, "
            "s.sessions_remaining, s.sessions_total, s.archived_at "
            "FROM subscriptions s "
            "LEFT JOIN players pl ON pl.player_id = s.player_id "
            "WHERE s.archived_at IS NOT NULL ORDER BY s.archived_at DESC"
        ).fetchall()
        if not rows:
            print("No archived subscriptions.")
            return
        print(f"{'ID':<6} {'Archived at':<20} {'Player':<25} {'Sess'}")
        print("-" * 70)
        for sid, name, act, rem, tot, at in rows:
            print(f"{sid:<6} {at:<20} {name or '?':<25} {rem}/{tot}")
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_archive.py archive <player_id>")
        print("  python test_archive.py restore <player_id>")
        print("  python test_archive.py list")
        print("  python test_archive.py archive_sub <subscription_id>")
        print("  python test_archive.py restore_sub <subscription_id>")
        print("  python test_archive.py list_subs")
        return

    cmd = sys.argv[1]

    if cmd == "archive" and len(sys.argv) == 3:
        archive_player(int(sys.argv[2]))
    elif cmd == "restore" and len(sys.argv) == 3:
        restore_player(int(sys.argv[2]))
    elif cmd == "list":
        list_archived_players()
    elif cmd == "archive_sub" and len(sys.argv) == 3:
        archive_subscription(int(sys.argv[2]))
    elif cmd == "restore_sub" and len(sys.argv) == 3:
        restore_subscription(int(sys.argv[2]))
    elif cmd == "list_subs":
        list_archived_subs()
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()