
# ---------------------------------------------------------
# 1. Verify the audit screen imports successfully
# ---------------------------------------------------------
from ui.screens.audit_screen import AuditScreen, _TypedConfirmDialog

print("audit_screen imports OK")


# ---------------------------------------------------------
# 2. Verify required audit service functions exist
# ---------------------------------------------------------
from services import audit_service

assert hasattr(audit_service, "query_ui"), (
    "audit_service is missing query_ui"
)

assert hasattr(audit_service, "clear"), (
    "audit_service is missing clear"
)

print("audit_service has query_ui + clear")


# ---------------------------------------------------------
# 3. Insert test rows to verify audit action labels
# ---------------------------------------------------------
from db.database import get_connection

connection = get_connection()

test_actions = (
    "championship.create",
    "player.update",
    "subscription.record_payment",
)

try:
    for action in test_actions:
        connection.execute(
            """
            INSERT INTO audit_log (
                username,
                action,
                target_type,
                target_id,
                details,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                "seed_manager",
                action,
                "test",
                1,
                '{"k": "v"}',
            ),
        )

    connection.commit()
finally:
    connection.close()

print("inserted 3 test rows")
