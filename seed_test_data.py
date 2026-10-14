"""
Heavy test-data seed script.

Populates the local Academy System database with realistic sample data
covering every feature area:

  - 3 activities with different training days
  - 20 players with varied profiles
  - Active, expired, and suspended subscriptions
  - Payments across cash / transfer / wallet, spread over ~90 days
  - Expenses across all categories, per month
  - Attendance logs (allowed / denied / override) over 60 days
  - New signups across the last 60 days
  - Audit log entries

Run once:
    python seed_test_data.py

WARNING: This ADDS to the current DB. To start clean, delete the DB first:

    Windows:
        del "%LOCALAPPDATA%\\AcademySystem\\academy.db"
    then run: python main.py    (rebuilds schema)
    then run: python seed_test_data.py

Safe to re-run? No. Running twice duplicates players and payments.
Delete the DB first if you want to re-seed.
"""

import os
import sys
import random
import string
from datetime import date, datetime, timedelta

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db.database import get_connection, init_db
from repositories import (
    players_repo, subscriptions_repo, payments_repo,
    activities_repo, expenses_repo, attendance_repo, audit_repo,
)
from repositories.players_repo import Player
from repositories.subscriptions_repo import Subscription
from repositories.activities_repo import Activity
from repositories.payments_repo import Payment
from repositories.expenses_repo import Expense


random.seed(42)   # deterministic output for reproducibility


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ARABIC_FIRST_NAMES = [
    "أحمد", "محمد", "محمود", "يوسف", "عمر", "علي", "حسن", "حسين",
    "سارة", "مريم", "نور", "ياسمين", "هنا", "جنى", "ملك", "ليلى",
    "كريم", "طارق", "زياد", "خالد", "سلمى", "رنا", "دينا", "فاطمة",
]

ARABIC_LAST_NAMES = [
    "محمد", "حسن", "علي", "إبراهيم", "سيد", "عبد الله", "مصطفى",
    "الشريف", "فؤاد", "كامل", "رشاد", "نبيل", "سمير", "أنور",
]

EN_FIRST_NAMES = [
    "Ahmed", "Mohamed", "Mahmoud", "Youssef", "Omar", "Ali", "Hassan",
    "Hussein", "Sara", "Mariam", "Nour", "Yasmin", "Hana", "Jana",
    "Malak", "Layla", "Karim", "Tarek", "Ziad", "Khaled", "Salma",
    "Rana", "Dina", "Fatma",
]

EN_LAST_NAMES = [
    "Mohamed", "Hassan", "Ali", "Ibrahim", "Sayed", "Abdullah",
    "Mostafa", "El-Sherif", "Fouad", "Kamel", "Rashad", "Nabil",
    "Samir", "Anwar",
]

# Activities to create. Names match the schema: name_en, name_ar, default_days
ACTIVITIES = [
    {
        "name_en": "Kung Fu",
        "name_ar": "الكونغ فو",
        "days": ["Monday", "Wednesday", "Friday"],
        "color": "#2563EB",
    },
    {
        "name_en": "Karate",
        "name_ar": "كاراتيه",
        "days": ["Sunday", "Tuesday", "Thursday"],
        "color": "#16A34A",
    },
    {
        "name_en": "Fitness",
        "name_ar": "لياقة بدنية",
        "days": ["Saturday", "Monday", "Wednesday"],
        "color": "#D97706",
    },
]

# Payment methods with realistic distribution
PAYMENT_METHODS = ["cash", "cash", "cash", "cash", "transfer", "wallet"]

# Expense categories with typical monthly amounts (EGP)
EXPENSE_TEMPLATES = [
    ("rent",       "إيجار القاعة الشهري",     5000),
    ("salaries",   "راتب المدرب أحمد",         3500),
    ("salaries",   "راتب المدرب مصطفى",         2800),
    ("utilities",  "فاتورة الكهرباء",            450),
    ("utilities",  "فاتورة المياه",              180),
    ("equipment",  "شراء معدات تدريب",          1200),
    ("other",      "مصروفات متنوعة",             300),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rand_phone():
    return "010" + "".join(random.choices(string.digits, k=8))


def rand_national_id():
    return "".join(random.choices(string.digits, k=14))


def rand_dob():
    """Random birthday between ages 5 and 16."""
    today = date.today()
    years_old = random.randint(5, 16)
    birth_year = today.year - years_old
    return date(birth_year, random.randint(1, 12), random.randint(1, 28))


def make_player_row(i: int) -> Player:
    """Create a Player dataclass with random but realistic data."""
    is_arabic = random.random() < 0.7
    if is_arabic:
        full_name = f"{random.choice(ARABIC_FIRST_NAMES)} {random.choice(ARABIC_LAST_NAMES)}"
    else:
        full_name = f"{random.choice(EN_FIRST_NAMES)} {random.choice(EN_LAST_NAMES)}"

    return Player(
        player_id=None,
        full_name=full_name,
        national_id=rand_national_id(),
        phone=rand_phone(),
        dob=rand_dob().isoformat(),
        photo_path=None,
        qr_code_path=None,          # will be set after insert (if you want real QRs)
        status="active",
        notes=None,
    )


# ---------------------------------------------------------------------------
# Seed steps
# ---------------------------------------------------------------------------

def seed_activities() -> dict:
    """
    Ensure the three activities exist. Returns dict {name_en: activity_id}.
    """
    print("\n[1/6] Activities")
    result = {}

    # The default DB has only "Kung Fu" seeded by migration 001.
    # Find or create each activity.
    existing = {a.name_en: a for a in activities_repo.list_all(include_inactive=True)}

    for spec in ACTIVITIES:
        if spec["name_en"] in existing:
            act = existing[spec["name_en"]]
            result[spec["name_en"]] = act.activity_id
            print(f"  ·  reused: {act.name_en} ({act.name_ar}) #{act.activity_id}")
        else:
            act = Activity(
                activity_id=None,
                name_en=spec["name_en"],
                name_ar=spec["name_ar"],
                default_days=spec["days"],
                color=spec["color"],
                active=True,
            )
            aid = activities_repo.create(act)
            result[spec["name_en"]] = aid
            print(f"  ·  created: {spec['name_en']} ({spec['name_ar']}) #{aid}")

    return result


def seed_players(count: int = 20) -> list:
    """
    Insert `count` players and return their full row objects with IDs.
    """
    print(f"\n[2/6] Players ({count})")
    ids = []
    for i in range(count):
        p = make_player_row(i)
        pid = players_repo.create(p)
        ids.append(pid)
        print(f"  ·  #{pid:>3}  {p.full_name}")
    return [players_repo.get_by_id(pid) for pid in ids]


def seed_subscriptions(players: list, activities: dict) -> list:
    """
    Give each player 1-2 subscriptions with a mix of states:

      ~60% active, not expired, sessions remaining
      ~15% expired (past expiry)
      ~10% suspended
      ~15% no subscription at all

    Returns the list of (player, [subscriptions]) tuples.
    """
    print("\n[3/6] Subscriptions")
    act_items = list(activities.items())
    today = date.today()
    results = []

    for i, player in enumerate(players):
        roll = random.random()

        if roll < 0.15:
            # No subscription
            results.append((player, []))
            print(f"  ·  {player.full_name}: no subscription")
            continue

        n_subs = 1 if random.random() < 0.8 else 2
        subs = []

        for _ in range(n_subs):
            act_name, act_id = random.choice(act_items)
            sessions_total = random.choice([4, 8, 12, 20])
            sessions_remaining = random.randint(0, sessions_total)
            start = today - timedelta(days=random.randint(5, 120))

            if roll < 0.75:
                # Active — expiry in the future, sessions remaining > 0
                expiry = today + timedelta(days=random.randint(3, 45))
                status = "active"
                sessions_remaining = max(1, sessions_remaining)
            elif roll < 0.90:
                # Expired — expiry in the past
                expiry = today - timedelta(days=random.randint(1, 30))
                status = "expired"
            else:
                # Suspended — expiry in the future, status suspended
                expiry = today + timedelta(days=random.randint(10, 45))
                status = "suspended"

            sub = Subscription(
                subscription_id=None,
                player_id=player.player_id,
                activity_id=act_id,
                plan_type=random.choice([None, "4", "8", "12"]),
                start_date=start.isoformat(),
                expiry_date=expiry.isoformat(),
                sessions_total=sessions_total,
                sessions_remaining=sessions_remaining,
                allowed_days=list(ACTIVITIES[0]["days"]),   # placeholder, overwritten below
                status=status,
                activated_by="manager",
                payment_amount=None,
                payment_date=None,
            )
            # Set allowed_days from the chosen activity
            for spec in ACTIVITIES:
                if spec["name_en"] == act_name:
                    sub.allowed_days = list(spec["days"])
                    break

            sid = subscriptions_repo.create(sub)
            sub.subscription_id = sid
            subs.append(sub)
            print(f"  ·  {player.full_name}: {act_name} {sessions_remaining}/{sessions_total} "
                  f"({status})")

        results.append((player, subs))

    return results


def seed_payments(player_subs: list) -> None:
    """
    For each player with subscriptions, generate 1-4 payments over the
    last 90 days. Payment methods vary. Also reactivates the linked
    subscription's payment_amount / payment_date for consistency.
    """
    print("\n[4/6] Payments")
    today = date.today()
    total_count = 0

    for player, subs in player_subs:
        if not subs:
            continue

        for sub in subs:
            n_payments = random.choices([1, 2, 3], weights=[70, 20, 10])[0]
            for _ in range(n_payments):
                amount = random.choice([300, 400, 500, 600, 700, 800, 1000, 1200])
                # Payment date somewhere between subscription start and today
                try:
                    sub_start = date.fromisoformat(sub.start_date)
                except Exception:
                    sub_start = today - timedelta(days=60)
                if sub_start > today:
                    sub_start = today - timedelta(days=30)
                days_range = (today - sub_start).days or 1
                pay_date = sub_start + timedelta(days=random.randint(0, days_range))

                method = random.choice(PAYMENT_METHODS)
                payment = Payment(
                    payment_id=None,
                    player_id=player.player_id,
                    subscription_id=sub.subscription_id,
                    amount=float(amount),
                    currency="EGP",
                    method=method,
                    payment_date=pay_date.isoformat(),
                    receipt_no=None,
                    notes=f"Seed payment ({method})",
                    recorded_by="manager",
                )
                payments_repo.create(payment)
                total_count += 1

                # Keep the subscription's denormalized fields in sync with
                # the LAST payment
                sub.payment_amount = float(amount)
                sub.payment_date = pay_date.isoformat()

    print(f"  ·  created {total_count} payment rows")


def seed_expenses() -> None:
    """
    Add the same 7 expenses to each of the last 3 months.
    """
    print("\n[5/6] Expenses")
    today = date.today()
    total = 0

    for months_ago in range(3):
        # Determine the anchor date for this month
        y = today.year
        m = today.month - months_ago
        while m <= 0:
            m += 12
            y -= 1
        # Use day 5 of that month
        try:
            d = date(y, m, 5)
        except ValueError:
            continue

        for category, description, base_amount in EXPENSE_TEMPLATES:
            # Add small variance
            variance = random.randint(-100, 200)
            amount = max(50, base_amount + variance)
            e = Expense(
                expense_id=None,
                category=category,
                description=description,
                amount=float(amount),
                currency="EGP",
                expense_date=d.isoformat(),
                recorded_by="manager",
            )
            expenses_repo.create(e)
            total += 1

    print(f"  ·  created {total} expense rows across 3 months")


def seed_attendance(player_subs: list) -> None:
    """
    Log attendance for the last 60 days. Most entries are allowed, a few
    denied, a few overrides. Matches training days for each subscription.
    """
    print("\n[6/6] Attendance log")
    today = date.today()
    total = 0

    weekday_names = {
        0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
        4: "Friday", 5: "Saturday", 6: "Sunday",
    }

    for player, subs in player_subs:
        if not subs:
            continue

        # Each player attends on ~70% of their training days
        for sub in subs:
            allowed_days = sub.allowed_days or []
            if not allowed_days:
                continue

            sub_start = date.fromisoformat(sub.start_date)
            sub_expiry = date.fromisoformat(sub.expiry_date)

            d = max(sub_start, today - timedelta(days=60))
            end = min(sub_expiry, today)

            while d <= end:
                if weekday_names[d.weekday()] in allowed_days:
                    roll = random.random()
                    if roll < 0.70:
                        # allowed
                        result = "allowed"
                        deny_reason = None
                        was_override = False
                        override_note = None
                        # Set the scan time to a plausible hour
                        hour = random.choice([17, 18, 19, 20, 21])
                        minute = random.randint(0, 59)
                        scan_dt = f"{d.isoformat()} {hour:02d}:{minute:02d}:00"
                        attendance_repo.log(
                            player_id=player.player_id,
                            subscription_id=sub.subscription_id,
                            result="allowed",
                            deny_reason=None,
                            recorded_by="manager",
                            was_override=False,
                            override_note=None,
                            scan_datetime=scan_dt,
                        )
                        total += 1
                    elif roll < 0.85:
                        # denied (typical reasons)
                        reason = random.choice([
                            "Not a training day for this plan (allowed: " +
                            ", ".join(allowed_days) + ")",
                            "No sessions remaining",
                        ])
                        hour = random.choice([17, 18, 19, 20, 21])
                        minute = random.randint(0, 59)
                        scan_dt = f"{d.isoformat()} {hour:02d}:{minute:02d}:00"
                        attendance_repo.log(
                            player_id=player.player_id,
                            subscription_id=sub.subscription_id,
                            result="denied",
                            deny_reason=reason,
                            recorded_by="manager",
                            was_override=False,
                            override_note=None,
                            scan_datetime=scan_dt,
                        )
                        total += 1
                    elif roll < 0.90:
                        # override
                        hour = random.choice([17, 18, 19, 20, 21])
                        minute = random.randint(0, 59)
                        scan_dt = f"{d.isoformat()} {hour:02d}:{minute:02d}:00"
                        attendance_repo.log(
                            player_id=player.player_id,
                            subscription_id=sub.subscription_id,
                            result="allowed",
                            deny_reason=None,
                            recorded_by="manager",
                            was_override=True,
                            override_note="Parent paid on the spot",
                            scan_datetime=scan_dt,
                        )
                        total += 1
                d += timedelta(days=1)

    print(f"  ·  created {total} attendance rows")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    init_db()

    # Warn if there are already players
    conn = get_connection()
    try:
        existing = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    finally:
        conn.close()

    if existing > 0:
        print(f"\nWARNING: {existing} players already exist.")
        print("Re-running this script will ADD data, not replace it.")
        ans = input("Continue anyway? [y/N] ").strip().lower()
        if ans != "y":
            print("Aborted.")
            return

    print("=" * 60)
    print("  Seeding test data — this may take 10–30 seconds.")
    print("=" * 60)

    activities = seed_activities()
    players = seed_players(count=20)
    player_subs = seed_subscriptions(players, activities)
    seed_payments(player_subs)
    seed_expenses()
    seed_attendance(player_subs)

    print()
    print("=" * 60)
    print("  Done. Open the app and explore the dashboards.")
    print("=" * 60)
    print()
    print("Login:  manager")
    print("Password (if first run): admin  (then set a real one)")
    print()
    print("Try these to test:")
    print("  · Dashboard → Daily → navigate dates, click chart bars")
    print("  · Dashboard → Monthly → switch months, see breakdowns")
    print("  · Players → search, filter, double-click a player")
    print("  · Player detail → Subscriptions table with multiple subs")
    print("  · Player detail → Records & Activity → print a PDF")
    print("  · Activities → see the 3 activities")
    print("  · Users → see the manager account")
    print("  · Audit → every action logged")
    print("  · Expenses → month-by-month list")
    print()


if __name__ == "__main__":
    main()