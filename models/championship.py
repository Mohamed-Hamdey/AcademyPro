"""
Championship models.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Championship:
    championship_id: Optional[int]
    name: str                  # <--- Replaces name_en and name_ar
    event_date: str
    location: Optional[str] = None
    entry_fee: float = 0.0
    notes: Optional[str] = None
    archived_at: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "Championship":
        keys = row.keys()
        return cls(
            championship_id=row["championship_id"],
            name=row["name"],  # <--- Read the new column
            event_date=row["event_date"],
            location=row["location"],
            entry_fee=row["entry_fee"],
            notes=row["notes"],
            archived_at=row["archived_at"] if "archived_at" in keys else None,
            created_at=row["created_at"] if "created_at" in keys else None,
        )


@dataclass
class ChampionshipParticipant:
    id: Optional[int]
    championship_id: int
    player_id: int
    weight_kg: Optional[float] = None
    belt: Optional[str] = None
    result: Optional[str] = None
    notes: Optional[str] = None
    registered_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "ChampionshipParticipant":
        return cls(
            id=row["id"],
            championship_id=row["championship_id"],
            player_id=row["player_id"],
            weight_kg=row["weight_kg"],
            belt=row["belt"],
            result=row["result"],
            notes=row["notes"],
            registered_at=row["registered_at"],
        )