"""
Migration 009 — indexes for report-heavy queries.

Adds indexes on columns used by the dashboard's aggregation queries
and by the audit log's date-range filters. These are the hottest
reads in the app, and on a database with 1,000+ rows they make the
difference between "instant" and "half-second lag".

Schema:
- subscriptions(player_id, status)  → player_list, dashboard
- attendance_log(activity_id)       → dashboard monthly reports
- payments(method)                  → dashboard reconciliation
"""

VERSION = 9
DESCRIPTION = "Report indexes"


def up(conn):
    # Composite index for the common "active subs for player X" query.
    # The plain index on player_id exists already; this one adds the
    # status column so the query can filter without a table scan.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_player_status "
        "ON subscriptions(player_id, status)"
    )

    # Activity filter for attendance reports.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_attendance_activity "
        "ON attendance_log(activity_id)"
    )

    # Payment method filter for reconciliation.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_payments_method "
        "ON payments(method)"
    )