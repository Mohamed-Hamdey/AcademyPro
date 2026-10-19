"""
Migration 007 — backfill payments from subscriptions.

Every existing subscription has a `payment_amount` and `payment_date`
denormalized onto the row. Going forward, payments are recorded in a
dedicated `payments` table (the ledger), so we can support:

  * partial payments
  * multiple payments on the same subscription
  * refunds (negative amounts)
  * payments not tied to any subscription (e.g. registration fees)

This migration copies the existing one-payment-per-subscription data into
the ledger so nothing is lost.

Idempotent: it only inserts a payment row for subscriptions that don't
already have a corresponding ledger entry (matched by subscription_id
+ matching amount + date).
"""

VERSION = 7
DESCRIPTION = "Backfill payments ledger from subscriptions"


def up(conn):
    # Which subs have a payment amount at all
    subs = conn.execute(
        """
        SELECT subscription_id, player_id, payment_amount, payment_date,
               activated_by, start_date
        FROM subscriptions
        WHERE payment_amount IS NOT NULL AND payment_amount > 0
        """
    ).fetchall()

    inserted = 0
    for sub in subs:
        sub_id = sub["subscription_id"]

        # Skip if a ledger entry already exists for this subscription
        existing = conn.execute(
            "SELECT 1 FROM payments WHERE subscription_id = ? LIMIT 1",
            (sub_id,),
        ).fetchone()
        if existing:
            continue

        payment_date = sub["payment_date"] or sub["start_date"]

        conn.execute(
            """
            INSERT INTO payments
                (player_id, subscription_id, amount, currency, method,
                 payment_date, receipt_no, notes, recorded_by)
            VALUES (?, ?, ?, 'EGP', 'cash', ?, NULL, ?, ?)
            """,
            (
                sub["player_id"],
                sub_id,
                float(sub["payment_amount"]),
                payment_date,
                "Backfilled from subscription",
                sub["activated_by"] or "system",
            ),
        )
        inserted += 1

    import logging
    logging.getLogger(__name__).info(
        "Backfilled %d payment(s) from subscriptions", inserted
    )