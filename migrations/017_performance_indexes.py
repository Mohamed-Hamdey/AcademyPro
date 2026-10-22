"""
Migration 017 — Performance indexes on hot columns.

Adds indexes on columns frequently used in WHERE, JOIN, and ORDER BY.
Massive speedup once the database grows past a few hundred rows.
"""

VERSION = 17
DESCRIPTION = "Performance indexes on hot columns"

def up(conn):
    indexes = [
        # Payments: filtered by date range, joined by player/subscription
        "CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date)",
        "CREATE INDEX IF NOT EXISTS idx_payments_player ON payments(player_id)",
        "CREATE INDEX IF NOT EXISTS idx_payments_subscription ON payments(subscription_id)",

        # Attendance: filtered by date range, joined by player/subscription/activity
        "CREATE INDEX IF NOT EXISTS idx_attendance_datetime ON attendance_log(scan_datetime)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_player ON attendance_log(player_id)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_subscription ON attendance_log(subscription_id)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_activity ON attendance_log(activity_id)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_result ON attendance_log(result)",

        # Subscriptions: filtered by status/expiry, joined by player/activity
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_player ON subscriptions(player_id)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_activity ON subscriptions(activity_id)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_expiry ON subscriptions(expiry_date)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_archived ON subscriptions(archived_at)",
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_sessions_remaining ON subscriptions(sessions_remaining)",

        # Players: filtered by archived_at (list vs recycle bin)
        "CREATE INDEX IF NOT EXISTS idx_players_archived ON players(archived_at)",
        "CREATE INDEX IF NOT EXISTS idx_players_name ON players(full_name)",

        # Championships: filtered by archived_at (list vs recycle bin)
        "CREATE INDEX IF NOT EXISTS idx_champs_archived ON championships(archived_at)",
        "CREATE INDEX IF NOT EXISTS idx_champs_event_date ON championships(event_date)",

        # Championship participants: joined by championship/player
        "CREATE INDEX IF NOT EXISTS idx_champ_participants_champ ON championship_players(championship_id)",
        "CREATE INDEX IF NOT EXISTS idx_champ_participants_player ON championship_players(player_id)",

        # Activities: filtered by active/archived
        "CREATE INDEX IF NOT EXISTS idx_activities_active ON activities(active)",
        "CREATE INDEX IF NOT EXISTS idx_activities_archived ON activities(archived_at)",

        # Expenses: filtered by date range
        "CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date)",
        "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)",

        # Player measurements: fetched by player for the history graph
        "CREATE INDEX IF NOT EXISTS idx_measurements_player ON player_measurements(player_id)",
        "CREATE INDEX IF NOT EXISTS idx_measurements_recorded_at ON player_measurements(recorded_at)",

        # Audit log: filtered by date range, action, username
        "CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)",
        "CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_log(username)",
    ]

    for sql in indexes:
        conn.execute(sql)