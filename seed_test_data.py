"""
Academy System — full test data seeder (v3).

Run from the project root:

    python seed_test_data.py              # seed everything
    python seed_test_data.py --reset      # wipe seed rows, re-seed
    python seed_test_data.py --what=users,activities,players
    python seed_test_data.py -v           # verbose

WHAT THIS SEEDS (idempotent — safe to re-run):

    users         2 managers + 2 receptionists + 1 tombstoned
    activities    3 activities (Kung Fu / Karate / Taekwondo)
    players       12 players (mixed Arabic/Latin, mixed statuses)
    subscriptions 8 active + 1 suspended + 1 expired + 1 low-sessions
    payments      one per subscription (via subscription_service.activate)
    attendance    3 today + 2 yesterday + 1 last week + 1 denied + 1 override
    expenses      5 expenses across categories over the past 30 days
    championships 1 championship linked to Kung Fu, with 4 participants

Safety:
    - All seeding goes through the app's own services, so payments land
      in the ledger, audit rows are written, and business rules apply.
    - The seeder sets `app_state` to the seeded manager while it runs,
      so any audit / recorded_by field shows "seed_manager" rather than
      "unknown".
    - `--reset` deletes ONLY seed rows (identified by SEED- IDs / names).
      It does NOT wipe the DB — safe to run alongside real data if any.
"""

from __future__ import annotations

import argparse
import os
import sys
import logging
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Trigger schema + migrations (main.py does the same).
from db import database  # noqa: F401, E402

from repositories import (
    activities_repo,
    players_repo,
    subscriptions_repo,
    championships_repo,
    expenses_repo,
    users_repo,
    attendance_repo,
)
from repositories.activities_repo import Activity
from repositories.expenses_repo import Expense
from models.player import Player
from models.subscription import Subscription
from models.championship import (
    Championship,
    ChampionshipParticipant,
)
from services import (
    auth_service,
    subscription_service,
    attendance_service,
)
from app_state import app as app_state

log = logging.getLogger("seed")

# ---------------------------------------------------------------------------
# Fixed identifiers
# ---------------------------------------------------------------------------

SEED_MANAGER_USERNAME    = "seed_manager"
SEED_MANAGER_PASSWORD    = "seed1234"
SEED_MANAGER_DISPLAY     = "مدير الاختبار (Seed)"

SEED_RECEPT_USERNAME     = "seed_reception"
SEED_RECEPT_PASSWORD     = "seed1234"
SEED_RECEPT_DISPLAY      = "موظف استقبال (Seed)"

SEED_MANAGER2_USERNAME   = "seed_manager2"
SEED_MANAGER2_PASSWORD   = "seed1234"
SEED_MANAGER2_DISPLAY    = "مدير إضافي (Seed)"

SEED_RECEPT2_USERNAME    = "seed_reception2"
SEED_RECEPT2_PASSWORD    = "seed1234"
SEED_RECEPT2_DISPLAY     = "استقبال إضافي (Seed)"

SEED_TOMBSTONE_USERNAME  = "seed_deleted"
SEED_TOMBSTONE_PASSWORD  = "seed1234"
SEED_TOMBSTONE_DISPLAY   = "مستخدم محذوف (Seed)"

# name_en is the unique key here (matches activities_repo.name_exists()).
SEED_ACTIVITIES = [
    # (name_ar, name_en, color, default_days)
    ("كونغ فو",  "SEED Kung Fu",  "#e74c3c", ["sat", "mon", "wed"]),
    ("كاراتيه",  "SEED Karate",   "#3498db", ["sun", "tue", "thu"]),
    ("تايكوندو", "SEED Taekwondo","#9b59b6", ["mon", "wed", "fri"]),
]

# National IDs are the idempotency key for players.
SEED_PLAYERS = [
    # (full_name, national_id, phone, dob, status, notes)
    ("أحمد محمد علي",       "SEED-0001", "01000000001", "2005-03-12", "active",    "لاعب اختبار"),
    ("محمد إبراهيم حسن",    "SEED-0002", "01000000002", "2003-07-22", "active",    None),
    ("فاطمة السيد",         "SEED-0003", "01000000003", "2007-11-04", "active",    None),
    ("يوسف عبد الرحمن",     "SEED-0004", "01000000004", "2001-01-15", "active",    None),
    ("مريم يوسف",           "SEED-0005", "01000000005", "2006-06-30", "active",    None),
    ("عمر خالد",            "SEED-0006", "01000000006", "2004-09-18", "active",    None),
    ("Ahmed Test Latin",    "SEED-0007", "01000000007", "1999-12-01", "active",    "Latin name test"),
    ("Sara Test Latin",     "SEED-0008", "01000000008", "2002-08-25", "suspended", "Suspended player test"),
    ("خالد سعيد",           "SEED-0009", "01000000009", "2008-02-14", "active",    None),
    ("نور الدين",           "SEED-0010", "01000000010", "2000-05-09", "active",    None),
    ("لاعب قديم (منتهي)",   "SEED-0011", "01000000011", "1998-04-20", "expired",   "Expired test"),
    ("لاعب بدون اشتراك",    "SEED-0012", "01000000012", "2005-10-10", "active",    "No sub — should show status=none"),
]

# Subscriptions to seed. Key is (player_national_id, activity_name_en).
# We use these to build a varied dataset — active / suspended / expired /
# low-sessions / multi-sub.
SEED_SUBSCRIPTIONS = [
    # (player_nid, activity_name_en, sessions_total, sessions_remaining,
    #  days_offset_start, days_offset_expiry, status, payment_amount)
    ("SEED-0001", "SEED Kung Fu",  12, 8,  -10,  20,  "active",   400.0),
    ("SEED-0002", "SEED Kung Fu",  12, 12, -5,   25,  "active",   400.0),
    ("SEED-0003", "SEED Karate",   16, 3,  -20,  10,  "active",   500.0),   # low-sessions (3 rem)
    ("SEED-0004", "SEED Taekwondo",8,  0,  -40,  -10, "expired",  300.0),   # expired
    ("SEED-0005", "SEED Kung Fu",  12, 6,  -15,  15,  "active",   400.0),
    ("SEED-0006", "SEED Karate",   8,  8,  -2,   28,  "active",   300.0),
    ("SEED-0007", "SEED Taekwondo",16, 10, -25,  5,   "active",   500.0),   # expiring soon
    ("SEED-0008", "SEED Kung Fu",  12, 4,  -30,  0,   "suspended",350.0),   # suspended (also player.status=suspended)
    ("SEED-0009", "SEED Karate",   8,  1,  -8,   22,  "active",   300.0),   # low-sessions (1 rem)
    ("SEED-0010", "SEED Kung Fu",  12, 12, -3,   27,  "active",   400.0),
    # Multi-sub: player 1 also has a Karate sub → exercises "multiple active"
    ("SEED-0001", "SEED Karate",   8,  8,  -4,   26,  "active",   300.0),
]

SEED_CHAMPIONSHIP = {
    "name": "SEED Spring Championship 2026",
    "event_date": "2026-04-15",
    "activity_name_en": "SEED Kung Fu",
    "location": "Nasr City Sports Hall",
    "entry_fee": 150.0,
    "notes": "Seeded championship for integration testing.",
}

# Attendance seeds keyed on (player_nid, days_ago, hour, result, deny_reason)
SEED_ATTENDANCE = [
    # (player_nid, days_ago, hour, minute, result, deny_reason, override_note)
    ("SEED-0001", 0, 9,  15, "allowed", None, None),
    ("SEED-0002", 0, 10, 30, "allowed", None, None),
    ("SEED-0005", 0, 11,  0, "allowed", None, None),
    ("SEED-0003", 1, 9,  45, "allowed", None, None),
    ("SEED-0006", 1, 17, 20, "allowed", None, None),
    ("SEED-0004", 7, 10, 10, "denied",  "expired", None),
    ("SEED-0008", 3, 16, 40, "allowed", None, "Manager override — suspension being reviewed"),
]

# Expense seeds: (days_ago, category, description, amount)
SEED_EXPENSES = [
    (1,  "rent",       "إيجار القاعة - الشهر الحالي",   3000.0),
    (5,  "equipment",  "شراء أحزمة تدريب",             850.0),
    (12, "utilities",  "فاتورة كهرباء",                 420.0),
    (20, "salaries",   "راتب المدرب المساعد",           2500.0),
    (28, "misc",       "مصاريف نظافة",                  150.0),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _become_seed_user():
    """
    Set app_state to the seed manager so any audit / payment rows created
    during seeding show `seed_manager` instead of `unknown`. Restored to
    None at the end via `_restore_user()`.
    """
    try:
        user = users_repo.get_by_username(SEED_MANAGER_USERNAME)
        if user is not None:
            app_state.set_user(user)
    except Exception:
        log.exception("Could not set app_state to seed manager (non-fatal)")


def _restore_user():
    try:
        app_state.clear()
    except Exception:
        pass


def _find_user(username: str):
    return users_repo.get_by_username(username)


def _find_activity(name_en: str):
    for a in activities_repo.list_all(include_inactive=True) or []:
        if (a.name or "").strip() == name_en.strip():
            return a
    return None


def _find_player(nid: str):
    return players_repo.get_by_national_id(nid)


def _find_championship(name: str):
    for c in championships_repo.list_championships(include_archived=True) or []:
        if c.name == name:
            return c
    return None


def _iso_shift(days_offset: int) -> str:
    return (date.today() + timedelta(days=days_offset)).isoformat()


def _dt_shift(days_ago: int, hour: int, minute: int) -> str:
    d = datetime.now() - timedelta(days=days_ago)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0) \
            .strftime("%Y-%m-%d %H:%M:%S")

# ---------------------------------------------------------------------------
# Seeders
# ---------------------------------------------------------------------------

def seed_users():
    log.info("Seeding users…")
    created, reused = 0, 0
    accounts = [
        (SEED_MANAGER_USERNAME,  SEED_MANAGER_DISPLAY,  SEED_MANAGER_PASSWORD,  "manager"),
        (SEED_MANAGER2_USERNAME, SEED_MANAGER2_DISPLAY, SEED_MANAGER2_PASSWORD, "manager"),
        (SEED_RECEPT_USERNAME,   SEED_RECEPT_DISPLAY,   SEED_RECEPT_PASSWORD,   "receptionist"),
        (SEED_RECEPT2_USERNAME,  SEED_RECEPT2_DISPLAY,  SEED_RECEPT2_PASSWORD,  "receptionist"),
    ]
    for username, display, password, role in accounts:
        if _find_user(username) is not None:
            reused += 1
            continue
        try:
            auth_service.create_user(username, display, password, role)
            created += 1
        except Exception:
            log.exception("Failed to create user %r", username)

    # One tombstoned user (soft-deleted) — so the Recycle Bin > Users tab
    # has content on first run. We tombstone immediately after creating.
    if _find_user(SEED_TOMBSTONE_USERNAME) is None and \
       not any(u.username.startswith("deleted_") and SEED_TOMBSTONE_DISPLAY in u.display_name
               for u in users_repo.list_tombstoned() or []):
        try:
            uid = auth_service.create_user(
                SEED_TOMBSTONE_USERNAME, SEED_TOMBSTONE_DISPLAY,
                SEED_TOMBSTONE_PASSWORD, "receptionist",
            )
            users_repo.tombstone(uid)
            created += 1
        except Exception:
            log.exception("Failed to create/tombstone user %r", SEED_TOMBSTONE_USERNAME)

    log.info("Users: %d created, %d already existed.", created, reused)


def seed_activities():
    log.info("Seeding activities…")
    created, reused = 0, 0
    for name_ar, name_en, color, default_days in SEED_ACTIVITIES:
        if _find_activity(name_en):
            reused += 1
            continue
        try:
            activities_repo.create(Activity(
                activity_id=None,
                name_en=name_en,
                name_ar=name_ar,
                default_days=list(default_days),
                color=color,
                active=True,
            ))
            created += 1
        except Exception:
            log.exception("Failed to create activity %r", name_en)
    log.info("Activities: %d created, %d already existed.", created, reused)


def seed_players():
    log.info("Seeding players…")
    created, reused = 0, 0
    for full_name, nid, phone, dob, status, notes in SEED_PLAYERS:
        if _find_player(nid):
            reused += 1
            continue
        try:
            players_repo.create(Player(
                player_id=None,
                full_name=full_name,
                national_id=nid,
                phone=phone,
                dob=dob,
                photo_path=None,
                qr_code_path=None,
                status=status,
                notes=notes,
            ))
            created += 1
        except Exception:
            log.exception("Failed to create player %r", full_name)
    log.info("Players: %d created, %d already existed.", created, reused)


def _has_sub(player_id: int, activity_id: int) -> bool:
    """Idempotency check — is there any non-archived sub for this pair?"""
    for s in subscriptions_repo.get_history_for_player(player_id) or []:
        if s.activity_id == activity_id:
            return True
    return False


def seed_subscriptions():
    log.info("Seeding subscriptions…")
    created, skipped = 0, 0
    for (nid, act_name, sessions_total, sessions_remaining,
         start_off, exp_off, status, amount) in SEED_SUBSCRIPTIONS:
        player = _find_player(nid)
        activity = _find_activity(act_name)
        if not player or not activity:
            log.warning("Skip sub: player=%s activity=%s not found", nid, act_name)
            skipped += 1
            continue
        if _has_sub(player.player_id, activity.activity_id):
            skipped += 1
            continue

        # Compute start/expiry. If already expired, we bypass
        # activate()'s 30-day-forward policy by writing directly, then
        # set status. Otherwise activate() computes expiry for us but
        # we override it to match the seed intent.
        start = date.today() + timedelta(days=start_off)
        want_expiry = date.today() + timedelta(days=exp_off)

        try:
            if status == "expired":
                # Write directly (activate() refuses past dates).
                sub_id = subscriptions_repo.create(Subscription(
                    subscription_id=None,
                    player_id=player.player_id,
                    activity_id=activity.activity_id,
                    start_date=start.isoformat(),
                    expiry_date=want_expiry.isoformat(),
                    sessions_total=sessions_total,
                    sessions_remaining=sessions_remaining,
                    allowed_days=list(activity.default_days or []),
                    plan_type=None,
                    status="expired",
                    activated_by=SEED_MANAGER_USERNAME,
                    payment_amount=amount,
                    payment_date=start.isoformat(),
                ))
            else:
                sub_id = subscription_service.activate(
                    player_id=player.player_id,
                    activity_id=activity.activity_id,
                    sessions_total=sessions_total,
                    allowed_days=list(activity.default_days or []),
                    start_date=start,
                    activated_by=SEED_MANAGER_USERNAME,
                    payment_amount=amount,
                    payment_date=start,
                )
                # Override expiry + sessions_remaining + status to match seed intent.
                subscriptions_repo.update_payment_and_expiry(
                    sub_id, amount, start.isoformat(),
                    want_expiry.isoformat(), status,
                )
                subscriptions_repo.set_sessions_remaining(sub_id, sessions_remaining)

            created += 1
        except Exception:
            log.exception("Failed to seed sub for player=%s activity=%s",
                          nid, act_name)
            skipped += 1
    log.info("Subscriptions: %d created, %d skipped.", created, skipped)


def seed_attendance():
    log.info("Seeding attendance…")
    created, skipped = 0, 0
    for (nid, days_ago, hour, minute, result, deny_reason, note) in SEED_ATTENDANCE:
        player = _find_player(nid)
        if not player:
            log.warning("Skip attendance: player=%s not found", nid)
            skipped += 1
            continue
        scan_dt = _dt_shift(days_ago, hour, minute)
        # Idempotency: same (player, exact datetime) check
        existing = attendance_repo.get_for_player(player.player_id) or []
        if any(a.scan_datetime == scan_dt for a in existing):
            skipped += 1
            continue
        # Attach a subscription for 'allowed' rows so undo logic works.
        active_subs = subscriptions_repo.get_all_active_for_player(player.player_id)
        sub_id = active_subs[0].subscription_id if active_subs else None
        try:
            attendance_service.log_attendance(
                player_id=player.player_id,
                subscription_id=sub_id,
                result=result,
                deny_reason=deny_reason,
                recorded_by=SEED_RECEPT_USERNAME,
                was_override=bool(note),
                override_note=note,
                scan_datetime=scan_dt,
            )
            created += 1
        except Exception:
            log.exception("Failed to seed attendance for %s @ %s", nid, scan_dt)
            skipped += 1
    log.info("Attendance: %d created, %d skipped.", created, skipped)


def seed_expenses():
    log.info("Seeding expenses…")
    created, skipped = 0, 0
    for (days_ago, category, description, amount) in SEED_EXPENSES:
        expense_date = _iso_shift(-days_ago)
        # Idempotency: match on (category, description, expense_date)
        existing = expenses_repo.list_for_date_range(expense_date, expense_date) or []
        if any(e.category == category and e.description == description
               for e in existing):
            skipped += 1
            continue
        try:
            expenses_repo.create(Expense(
                expense_id=None,
                category=category,
                description=description,
                amount=amount,
                currency="EGP",
                expense_date=expense_date,
                recorded_by=SEED_MANAGER_USERNAME,
            ))
            created += 1
        except Exception:
            log.exception("Failed to seed expense %r", description)
            skipped += 1
    log.info("Expenses: %d created, %d skipped.", created, skipped)


def seed_championship():
    log.info("Seeding championship…")
    existing = _find_championship(SEED_CHAMPIONSHIP["name"])
    if existing:
        log.info("Championship already exists (id=%s).", existing.championship_id)
        return existing

    activity = _find_activity(SEED_CHAMPIONSHIP["activity_name_en"])
    if not activity:
        log.error("Cannot seed championship: activity %r missing.",
                  SEED_CHAMPIONSHIP["activity_name_en"])
        return None

    cid = championships_repo.create_championship(Championship(
        championship_id=None,
        name=SEED_CHAMPIONSHIP["name"],
        event_date=SEED_CHAMPIONSHIP["event_date"],
        activity_id=activity.activity_id,
        location=SEED_CHAMPIONSHIP["location"],
        entry_fee=SEED_CHAMPIONSHIP["entry_fee"],
        notes=SEED_CHAMPIONSHIP["notes"],
    ))
    log.info("Championship created (id=%s).", cid)
    return championships_repo.get_championship(cid)


def seed_championship_participants(champ):
    if champ is None:
        return
    log.info("Seeding championship participants…")
    eligible = players_repo.list_with_details_for_activity(champ.activity_id)
    eligible_ids = [r["player"].player_id for r in eligible]
    if not eligible_ids:
        log.warning("No eligible players for championship — skipping participants.")
        return

    existing = {p["player_id"]
                for p in championships_repo.list_participants(champ.championship_id)}
    belts   = ["white", "yellow", "orange", "green", "blue", "brown", "black"]
    weights = [55, 60, 65, 70, 75, 80]
    results = [None, None, "gold", None, "silver", "bronze"]

    assigned = 0
    for i, pid in enumerate(eligible_ids[:6]):
        if pid in existing:
            continue
        try:
            championships_repo.add_participant(ChampionshipParticipant(
                id=None,
                championship_id=champ.championship_id,
                player_id=pid,
                weight_kg=weights[i % len(weights)],
                belt=belts[i % len(belts)],
                result=results[i % len(results)],
                notes="Seeded participant",
            ))
            assigned += 1
        except Exception:
            log.exception("Failed to add participant player_id=%s", pid)
    log.info("Participants: %d assigned.", assigned)


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def reset_seed_data():
    from db.database import get_connection
    log.warning("Reset requested — deleting seed rows…")
    conn = get_connection()
    try:
        # Championship + participants
        row = conn.execute(
            "SELECT championship_id FROM championships WHERE name = ?",
            (SEED_CHAMPIONSHIP["name"],),
        ).fetchone()
        if row:
            cid = row["championship_id"]
            conn.execute("DELETE FROM championship_players WHERE championship_id = ?", (cid,))
            conn.execute("DELETE FROM championships WHERE championship_id = ?", (cid,))

        # Expenses (by seed descriptions)
        for _, _, description, _ in SEED_EXPENSES:
            conn.execute("DELETE FROM expenses WHERE description = ?", (description,))

        # Attendance — match by recorded_by=seed_reception
        conn.execute("DELETE FROM attendance_log WHERE recorded_by = ?",
                     (SEED_RECEPT_USERNAME,))

        # Subscriptions + payments — match by activated_by=seed_manager
        sub_rows = conn.execute(
            "SELECT subscription_id FROM subscriptions WHERE activated_by = ?",
            (SEED_MANAGER_USERNAME,),
        ).fetchall()
        for r in sub_rows:
            sid = r["subscription_id"]
            conn.execute("DELETE FROM payments WHERE subscription_id = ?", (sid,))
            conn.execute("DELETE FROM subscriptions WHERE subscription_id = ?", (sid,))

        # Activities (by name_en)
        for _, name_en, _, _ in SEED_ACTIVITIES:
            conn.execute("DELETE FROM activities WHERE name_en = ?", (name_en,))

        # Players (by national_id)
        for _, nid, _, _, _, _ in SEED_PLAYERS:
            conn.execute("DELETE FROM players WHERE national_id = ?", (nid,))

        # Users (by username), incl. tombstoned variant of seed_deleted
        for uname in (SEED_MANAGER_USERNAME, SEED_MANAGER2_USERNAME,
                      SEED_RECEPT_USERNAME, SEED_RECEPT2_USERNAME,
                      SEED_TOMBSTONE_USERNAME):
            conn.execute("DELETE FROM users WHERE username = ?", (uname,))
        conn.execute(
            "DELETE FROM users WHERE username LIKE 'deleted_%' "
            "AND display_name LIKE ?",
            (f"%{SEED_TOMBSTONE_DISPLAY}%",),
        )

        conn.commit()
    finally:
        conn.close()
    log.info("Reset complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

SEEDERS = {
    "users":         seed_users,
    "activities":    seed_activities,
    "players":       seed_players,
    "subscriptions": seed_subscriptions,
    "attendance":    seed_attendance,
    "expenses":      seed_expenses,
    "championships": lambda: seed_championship_participants(seed_championship()),
}

# Order matters — each step depends on the previous.
ORDERED_KEYS = [
    "users", "activities", "players", "subscriptions",
    "attendance", "expenses", "championships",
]


def main():
    ap = argparse.ArgumentParser(description="Seed Academy System test data.")
    ap.add_argument("--reset", action="store_true", help="Delete seed rows first.")
    ap.add_argument("--what", default=",".join(ORDERED_KEYS),
                    help=f"Comma-separated subset of: {', '.join(ORDERED_KEYS)}")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(name)s: %(message)s",
    )

    if args.reset:
        reset_seed_data()

    wanted = [w.strip() for w in args.what.split(",") if w.strip()]
    unknown = [w for w in wanted if w not in SEEDERS]
    if unknown:
        log.error("Unknown --what values: %s", unknown)
        sys.exit(2)

    _become_seed_user()
    try:
        # Run in canonical order regardless of --what order.
        for key in ORDERED_KEYS:
            if key in wanted:
                SEEDERS[key]()
    finally:
        _restore_user()

    log.info("Done.")


if __name__ == "__main__":
    main()