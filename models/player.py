"""
Player model — pure dataclass, no SQL.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Player:
    player_id: Optional[int]
    full_name: str
    national_id: Optional[str] = None
    phone: str = ""
    dob: str = ""
    photo_path: Optional[str] = None
    qr_code_path: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None
    archived_at: Optional[str] = None
    belt: Optional[str] = None
    weight_kg: Optional[float] = None
    session_time: Optional[str] = None   # <--- NEW

    @classmethod
    def from_row(cls, row) -> "Player":
        keys = row.keys() if hasattr(row, "keys") else []
        return cls(
            player_id=row["player_id"],
            full_name=row["full_name"],
            national_id=row["national_id"],
            phone=row["phone"],
            dob=row["dob"],
            photo_path=row["photo_path"],
            qr_code_path=row["qr_code_path"],
            status=row["status"],
            notes=row["notes"],
            archived_at=row["archived_at"] if "archived_at" in keys else None,
            belt=row["belt"] if "belt" in keys else None,
            weight_kg=row["weight_kg"] if "weight_kg" in keys else None,
            session_time=row["session_time"] if "session_time" in keys else None, # <--- NEW
        )