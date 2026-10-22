from datetime import date
from repositories import players_repo
from services import audit_service

def record_measurement(player_id: int, weight_kg: float, belt: str, notes: str = None):
    """Record a new measurement and update the player's current stats."""
    today_str = date.today().isoformat()
    
    # 1. Add to history
    players_repo.add_measurement(player_id, today_str, weight_kg, belt, notes)
    
    # 2. Update the player's current profile so the rest of the app sees the new values
    player = players_repo.get_by_id(player_id)
    if player:
        player.weight_kg = weight_kg
        player.belt = belt
        players_repo.update(player)
        
    # 3. Audit log
    audit_service.record(
        "player.measurement",
        target_type="player",
        target_id=player_id,
        details={"weight_kg": weight_kg, "belt": belt}
    )