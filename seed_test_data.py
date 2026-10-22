"""
seed_v4_test.py — Generates realistic test data for Academy System v4.
Run: python seed_v4_test.py
"""
import os
import sys
import random
from datetime import date, timedelta

# Ensure paths are setup
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db.database import init_db
from repositories import players_repo, activities_repo
from services import (
    auth_service, activity_service, championship_service, 
    expense_service, subscription_service, player_service
)
from models.player import Player
from models.championship import Championship, ChampionshipParticipant

def clear_db():
    print("Wiping database for a clean slate...")
    db_path = os.path.join(os.path.dirname(__file__), "academy.db")
    # Use the actual AppPaths if possible
    try:
        from paths import AppPaths
        db_path = AppPaths.database()
    except ImportError:
        pass
        
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db()

def seed():
    print("Starting v4 Seed...")
    
    # 1. USERS
    print("Creating users...")
    try:
        auth_service.create_user("manager", "المدير العام", "1234", "manager")
        auth_service.create_user("reception1", "أحمد الاستقبال", "1234", "receptionist")
        auth_service.create_user("reception2", "سارة الاستقبال", "1234", "receptionist")
    except Exception as e:
        print(f"Users might already exist: {e}")

    # 2. ACTIVITIES
    print("Creating activities...")
    # Karate: Requires belt & weight
    karate_id = activity_service.create(
        name="Karate", 
        default_days=["Monday", "Wednesday"], 
        color="#EF4444", 
        requires_belt=True, 
        requires_weight=True
    )
    # Football: Requires weight only
    football_id = activity_service.create(
        name="Football", 
        default_days=["Tuesday", "Thursday"], 
        color="#3B82F6", 
        requires_belt=False, 
        requires_weight=True
    )
    # Gymnastics: Requires neither
    gym_id = activity_service.create(
        name="Gymnastics", 
        default_days=["Saturday"], 
        color="#F59E0B", 
        requires_belt=False, 
        requires_weight=False
    )

    # 3. PLAYERS (100)
    print("Creating 100 players (this may take a moment)...")
    first_names = ["Ahmed", "Mohamed", "Omar", "Khaled", "Youssef", "Mostafa", "Ali", "Hassan", "Hussein", "Amr"]
    last_names = ["Ibrahim", "Mahmoud", "Sayed", "Fathy", "Zaki", "Nour", "Adel", "Samir", "Fouad", "Rami"]
    belts = ["white", "yellow", "orange", "green", "blue", "brown", "black"]
    times = ["18:00", "19:30", "21:00", None, "17:45"]
    
    players = []
    for i in range(1, 101):
        name = f"{random.choice(first_names)} {random.choice(last_names)} {i}"
        phone = f"010{random.randint(10000000, 99999999)}"
        
        # 30% chance of having a belt/weight recorded initially
        belt = random.choice(belts) if random.random() < 0.3 else None
        weight = round(random.uniform(30.0, 90.0), 1) if random.random() < 0.3 else None
        session_time = random.choice(times)
        
        p = Player(
            player_id=None,
            full_name=name,
            national_id=f"290{random.randint(100000000, 999999999)}",
            phone=phone,
            dob=f"20{random.randint(10, 20)}-0{random.randint(1,9)}-1{random.randint(0,9)}",
            belt=belt,
            weight_kg=weight,
            session_time=session_time
        )
        pid = players_repo.create(p)
        players.append(pid)

        # 50% chance to record 1-3 measurements (weight/belt history)
        if random.random() < 0.5:
            num_measurements = random.randint(1, 3)
            current_weight = random.uniform(30.0, 60.0)
            for m in range(num_measurements):
                current_weight += random.uniform(0.5, 3.0)
                m_date = (date.today() - timedelta(days=(num_measurements - m) * 30)).isoformat()
                m_belt = random.choice(belts)
                players_repo.add_measurement(pid, m_date, round(current_weight, 1), m_belt)

    # 4. SUBSCRIPTIONS (Varied)
    print("Creating subscriptions...")
    today = date.today()
    for pid in players:
        # 80% chance to have an active subscription
        if random.random() < 0.8:
            act_id = random.choice([karate_id, football_id, gym_id])
            start_date = today - timedelta(days=random.randint(0, 60))
            plan = random.choice(["4", "8", "12", None])
            sessions_total = int(plan) if plan else random.randint(5, 15)
            
            try:
                subscription_service.activate(
                    player_id=pid,
                    activity_id=act_id,
                    sessions_total=sessions_total,
                    allowed_days=["Monday", "Wednesday"],
                    start_date=start_date,
                    activated_by="seed",
                    payment_amount=random.choice([500, 800, 1200]),
                    payment_date=start_date,
                    plan_type=plan
                )
            except Exception as e:
                pass # Skip if duplicate or validation fails

    # 5. EXPENSES
    print("Creating expenses...")
    categories = ["rent", "salaries", "utilities", "equipment", "other"]
    for i in range(20):
        exp_date = today - timedelta(days=random.randint(0, 90))
        expense_service.create(
            category=random.choice(categories),
            description=f"Expense {i+1}",
            amount=random.choice([150.0, 300.0, 500.0, 1000.0]),
            expense_date=exp_date
        )

    # 6. CHAMPIONSHIPS
    print("Creating championships...")
    champ1_id = championship_service.create_championship(
        "Spring Karate Cup", 
        (today - timedelta(days=10)).isoformat(), 
        karate_id, 
        "Main Hall", 
        100.0, 
        "Annual spring tournament"
    )
    champ2_id = championship_service.create_championship(
        "Summer Football League", 
        (today + timedelta(days=20)).isoformat(), 
        football_id, 
        "Outdoor Field", 
        50.0, 
        "Upcoming summer league"
    )

    # Assign players to championship 1 (past)
    karate_players = players[:20] # First 20 players
    for pid in karate_players:
        try:
            p = players_repo.get_by_id(pid)
            cp = ChampionshipParticipant(
                id=None, 
                championship_id=champ1_id, 
                player_id=pid, 
                weight_kg=p.weight_kg or 60.0, 
                belt=p.belt or "white", 
                result=random.choice(["gold", "silver", "bronze", "participant"]),
                notes=None
            )
            championships_repo.add_participant(cp)
        except Exception:
            pass

    print("✅ Database seeded successfully!")
    print(f"Total Players: {len(players)}")
    print("Users: manager (1234), reception1 (1234), reception2 (1234)")

if __name__ == "__main__":
    clear_db()
    seed()