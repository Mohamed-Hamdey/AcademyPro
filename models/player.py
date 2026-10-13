"""
Player model — pure dataclass, no SQL.

Note: the `player_group` field has been removed (activities replace
groups). Any code that used to reference it now uses the subscription's
activity instead.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Player:
    player_id: Optional[int]
    full_name: str
    national_id: Optional[str]
    phone: str
    dob: str
    photo_path: Optional[str]
    qr_code_path: Optional[str]
    status: str = "active"
    notes: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "Player":
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
        )