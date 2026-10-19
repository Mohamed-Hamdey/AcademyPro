"""
Championship service.
"""

from models.championship import Championship, ChampionshipParticipant
from repositories import championships_repo
from services import payment_service
from datetime import date
import logging

def create_championship(name, event_date, activity_id, location, entry_fee, notes) -> int:
    if not name:
        raise ValueError("Name is required.")
    if not event_date:
        raise ValueError("Date is required.")
        
    champ = Championship(
        championship_id=None,
        name=name,
        event_date=event_date,
        activity_id=activity_id,
        location=location,
        entry_fee=entry_fee,
        notes=notes
    )
    return championships_repo.create_championship(champ)

def update_championship(champ_id, name, event_date, activity_id, location, entry_fee, notes) -> None:
    if not name:
        raise ValueError("Name is required.")
        
    champ = Championship(
        championship_id=champ_id,
        name=name,
        event_date=event_date,
        activity_id=activity_id,
        location=location,
        entry_fee=entry_fee,
        notes=notes
    )
    championships_repo.update_championship(champ)

def get_participants(champ_id: int) -> list[dict]:
    return championships_repo.list_participants(champ_id)

def register_player(champ_id: int, player_id: int, weight: float, belt: str, notes: str, record_payment: bool = True) -> int:
    """
    Registers a player. If the championship has an entry fee and 
    record_payment is True, it logs a payment in the ledger.
    """
    champ = championships_repo.get_championship(champ_id)
    if not champ:
        raise ValueError("Championship not found.")

    # 1. Register the player
    p = ChampionshipParticipant(
        id=None,
        championship_id=champ_id,
        player_id=player_id,
        weight_kg=weight,
        belt=belt,
        result=None,
        notes=notes
    )
    p_id = championships_repo.add_participant(p)

    # 2. Record payment (if applicable)
    if record_payment and champ.entry_fee > 0:
        try:
            payment_service.record(
                player_id=player_id,
                amount=champ.entry_fee,
                payment_date=date.fromisoformat(champ.event_date),
                method="cash",
                notes=f"Entry fee for {champ.name}",   # ← FIX: was champ.name_en
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to record championship payment"
            )

    return p_id