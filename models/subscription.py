"""
Subscription model — pure dataclass, no SQL.

A subscription now belongs to a specific activity and carries its own
sessions_total and allowed_days, independent of any plan.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Subscription:
    subscription_id: Optional[int]
    player_id: int
    activity_id: Optional[int]           # NEW: which activity this sub is for
    start_date: str
    expiry_date: str
    sessions_total: int
    sessions_remaining: int
    allowed_days: list = field(default_factory=list)   # NEW: per-player days
    plan_type: Optional[str] = None      # legacy: may be a preset key or None
    status: str = "active"
    activated_by: Optional[str] = None
    payment_amount: Optional[float] = None
    payment_date: Optional[str] = None
    archived_at: Optional[str] = None


    @classmethod
    def from_row(cls, row) -> "Subscription":
        import json
        keys = row.keys() if hasattr(row, "keys") else []

        # allowed_days is stored as JSON text
        allowed_days = []
        if "allowed_days" in keys and row["allowed_days"]:
            try:
                allowed_days = json.loads(row["allowed_days"])
            except (ValueError, TypeError):
                allowed_days = []

        return cls(
            subscription_id=row["subscription_id"],
            player_id=row["player_id"],
            activity_id=row["activity_id"] if "activity_id" in keys else None,
            start_date=row["start_date"],
            expiry_date=row["expiry_date"],
            sessions_total=row["sessions_total"],
            sessions_remaining=row["sessions_remaining"],
            allowed_days=allowed_days,
            plan_type=row["plan_type"] if "plan_type" in keys else None,
            status=row["status"],
            activated_by=row["activated_by"],
            payment_amount=row["payment_amount"],
            payment_date=row["payment_date"],
            archived_at=(
            row["archived_at"] if "archived_at" in row.keys() else None
            ),
        )