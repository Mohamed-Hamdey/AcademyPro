"""
Migration 001 — v2 initial schema.

This replaces the v1 schema entirely. Since v2 is a fresh start (v1 data
was demo-only and will be wiped), this migration creates all tables from
scratch and drops the old ones first if they exist.

Design notes:

- `players` — the same core fields as v1, plus an `archived` flag.
- `activities` — new. A sport/class (Karate, Kung Fu, Fitness, etc.).
  Soft-deleted via `active`. Has `default_days` (JSON list of weekday
  names) used when creating new subscriptions unless overridden.
- `subscriptions` — one row per player-activity enrollment. Sessions
  count is per-row. `allowed_days` is stored as JSON on the row so
  per-player overrides are possible.
- `payments` — every payment is its own row. Supports partial, refunds,
  multiple methods. `receipt_no` is optional, auto-generated on insert
  if not supplied.
- `expenses` — manager-entered outgoings (rent, salaries, equipment).
- `users` — login accounts. `role` is 'manager' or 'receptionist'.
- `audit_log` — every admin action worth remembering.
- `attendance_log` — same shape as v1, plus `activity_id` for reporting.
- `daily_close` / `monthly_close` — snapshots for locking financials.
- `settings` — key-value store for things like "academy name" once we
  move config out of the bundle.
"""

VERSION = 1
DESCRIPTION = "v2 initial schema"


def up(conn):
    # --- Drop v1 tables (fresh start) ---
    conn.executescript(
        """
        DROP TABLE IF EXISTS attendance_log;
        DROP TABLE IF EXISTS payments;
        DROP TABLE IF EXISTS subscriptions;
        DROP TABLE IF EXISTS player_activities;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS activities;
        DROP TABLE IF EXISTS expenses;
        DROP TABLE IF EXISTS audit_log;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS sessions;
        DROP TABLE IF EXISTS daily_close;
        DROP TABLE IF EXISTS monthly_close;
        DROP TABLE IF EXISTS settings;
        """
    )

    # --- Players ---
    conn.executescript(
        """
        CREATE TABLE players (
            player_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT NOT NULL,
            national_id   TEXT UNIQUE,
            phone         TEXT NOT NULL,
            dob           TEXT NOT NULL,
            photo_path    TEXT,
            notes         TEXT,
            archived      INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX idx_players_name ON players(full_name);
        CREATE INDEX idx_players_phone ON players(phone);
        """
    )

    # --- Activities ---
    conn.executescript(
        """
        CREATE TABLE activities (
            activity_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name_en       TEXT NOT NULL,
            name_ar       TEXT NOT NULL,
            default_days  TEXT NOT NULL,      -- JSON: ["Monday","Wednesday"]
            color         TEXT,               -- optional hex for UI badge
            active        INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE UNIQUE INDEX idx_activities_name_en ON activities(name_en) WHERE active = 1;
        """
    )

    # --- Subscriptions ---
    conn.executescript(
        """
        CREATE TABLE subscriptions (
            subscription_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id         INTEGER NOT NULL,
            activity_id       INTEGER NOT NULL,
            start_date        TEXT NOT NULL,
            expiry_date       TEXT NOT NULL,
            sessions_total    INTEGER NOT NULL,
            sessions_remaining INTEGER NOT NULL,
            allowed_days      TEXT NOT NULL,   -- JSON: ["Monday","Wednesday"]
            status            TEXT NOT NULL DEFAULT 'active',
                              -- active | expired | suspended | completed
            activated_by      TEXT,            -- username
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (player_id)   REFERENCES players(player_id),
            FOREIGN KEY (activity_id) REFERENCES activities(activity_id)
        );

        CREATE INDEX idx_subscriptions_player ON subscriptions(player_id);
        CREATE INDEX idx_subscriptions_activity ON subscriptions(activity_id);
        """
    )

    # --- Payments ---
    conn.executescript(
        """
        CREATE TABLE payments (
            payment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id       INTEGER NOT NULL,
            subscription_id INTEGER,           -- nullable: fees not tied to a sub
            amount          REAL NOT NULL,
            currency        TEXT NOT NULL DEFAULT 'EGP',
            method          TEXT NOT NULL DEFAULT 'cash',
                            -- cash | transfer | card | other
            payment_date    TEXT NOT NULL,
            receipt_no      TEXT,
            notes           TEXT,
            recorded_by     TEXT NOT NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (player_id)       REFERENCES players(player_id),
            FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id)
        );

        CREATE INDEX idx_payments_player ON payments(player_id);
        CREATE INDEX idx_payments_date ON payments(payment_date);
        """
    )

    # --- Expenses ---
    conn.executescript(
        """
        CREATE TABLE expenses (
            expense_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            category      TEXT NOT NULL,       -- rent | salaries | equipment | other
            description   TEXT NOT NULL,
            amount        REAL NOT NULL,
            currency      TEXT NOT NULL DEFAULT 'EGP',
            expense_date  TEXT NOT NULL,
            recorded_by   TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX idx_expenses_date ON expenses(expense_date);
        """
    )

    # --- Users (roles) ---
    conn.executescript(
        """
        CREATE TABLE users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            display_name  TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL,       -- manager | receptionist
            active        INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            last_login    TEXT
        );
        """
    )

    # --- Audit log ---
    conn.executescript(
        """
        CREATE TABLE audit_log (
            audit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            username      TEXT NOT NULL,
            action        TEXT NOT NULL,       -- e.g. "subscription.suspend"
            target_type   TEXT,                -- player | subscription | activity | user
            target_id     INTEGER,
            details       TEXT,                -- JSON blob with before/after
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE INDEX idx_audit_user ON audit_log(user_id);
        CREATE INDEX idx_audit_date ON audit_log(created_at);
        """
    )

    # --- Attendance log ---
    conn.executescript(
        """
        CREATE TABLE attendance_log (
            log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id       INTEGER NOT NULL,
            subscription_id INTEGER,
            activity_id     INTEGER,
            scan_datetime   TEXT NOT NULL,
            result          TEXT NOT NULL,     -- allowed | denied
            deny_reason     TEXT,
            was_override    INTEGER NOT NULL DEFAULT 0,
            override_note   TEXT,
            recorded_by     TEXT,
            FOREIGN KEY (player_id)       REFERENCES players(player_id),
            FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id),
            FOREIGN KEY (activity_id)     REFERENCES activities(activity_id)
        );

        CREATE INDEX idx_attendance_player ON attendance_log(player_id);
        CREATE INDEX idx_attendance_date ON attendance_log(scan_datetime);
        """
    )

    # --- Daily / monthly close ---
    conn.executescript(
        """
        CREATE TABLE daily_close (
            close_date      TEXT PRIMARY KEY,
            revenue         REAL NOT NULL DEFAULT 0,
            expenses        REAL NOT NULL DEFAULT 0,
            new_players     INTEGER NOT NULL DEFAULT 0,
            total_checkins  INTEGER NOT NULL DEFAULT 0,
            closed_by       TEXT NOT NULL,
            closed_at       TEXT NOT NULL DEFAULT (datetime('now')),
            notes           TEXT
        );

        CREATE TABLE monthly_close (
            close_month     TEXT PRIMARY KEY,  -- YYYY-MM
            revenue         REAL NOT NULL DEFAULT 0,
            expenses        REAL NOT NULL DEFAULT 0,
            closed_by       TEXT NOT NULL,
            closed_at       TEXT NOT NULL DEFAULT (datetime('now')),
            notes           TEXT
        );
        """
    )

    # --- Settings (key-value) ---
    conn.executescript(
        """
        CREATE TABLE settings (
            key    TEXT PRIMARY KEY,
            value  TEXT NOT NULL
        );
        """
    )

    # --- Seed: a default activity so the app isn't empty on first launch ---
    conn.execute(
        """
        INSERT INTO activities (name_en, name_ar, default_days)
        VALUES (?, ?, ?)
        """,
        ("Kung Fu", "الكونغ فو", '["Monday","Wednesday","Friday"]'),
    )

    # --- Seed: default manager account ---
    # Password is "admin" (bcrypt hash will be created by the app on first
    # login — until we add password hashing in Phase 1, this is a
    # placeholder that the login screen will recognize and force a reset.)
    conn.execute(
        """
        INSERT INTO users (username, display_name, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        ("manager", "المدير", "PLACEHOLDER_TO_BE_REPLACED", "manager"),
    )