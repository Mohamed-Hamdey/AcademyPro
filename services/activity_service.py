"""
Activity service — business logic for activities.

Wraps the repository with validation, localized name lookups, and a
"safe delete" that checks for references before deactivating.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from repositories import activities_repo
from repositories.activities_repo import Activity
from ui import i18n


def list_active() -> list[Activity]:
    return activities_repo.list_all(include_inactive=False)


def list_all() -> list[Activity]:
    return activities_repo.list_all(include_inactive=True)


def get(activity_id: int) -> Activity | None:
    return activities_repo.get_by_id(activity_id)


def get_localized_name(activity) -> str:
    if hasattr(activity, "name"):
        return activity.name
    return "—"


def create(name: str, default_days: list, color: str = None, requires_belt: bool = True, requires_weight: bool = True) -> int:
    """Create a new activity."""
    # (Keep whatever validation you have here, e.g., name_exists)
    
    # Pass the new parameters to the repo
    return activities_repo.create(
        name=name, 
        default_days=default_days, 
        color=color, 
        requires_belt=requires_belt, 
        requires_weight=requires_weight
    )

def update(activity_id: int, name: str, default_days: list, color: str = None, requires_belt: bool = True, requires_weight: bool = True) -> None:
    """Update an existing activity."""
    # (Keep whatever validation you have here)
    
    activities_repo.update(
        activity_id=activity_id, 
        name=name, 
        default_days=default_days, 
        color=color, 
        requires_belt=requires_belt, 
        requires_weight=requires_weight
    )

def deactivate(activity_id: int) -> None:
    activities_repo.set_active(activity_id, False)
    try:
        from services import audit_service
        audit_service.record("activity.archive", target_type="activity", target_id=activity_id)
    except Exception:
        pass


def reactivate(activity_id: int) -> None:
    activities_repo.set_active(activity_id, True)
    try:
        from services import audit_service
        audit_service.record("activity.restore", target_type="activity", target_id=activity_id)
    except Exception:
        pass


def count_references(activity_id: int) -> int:
    """How many subscriptions reference this activity (for the delete
    confirmation message)."""
    return activities_repo.count_active_subscriptions(activity_id)

def count_active_references(activity_id: int) -> int:
    """Number of subscriptions for this activity with status='active'."""
    return activities_repo.count_active_subscriptions_by_status(activity_id)

def delete(activity_id: int) -> None:
    refs = count_references(activity_id)
    if refs > 0:
        raise ValueError("Cannot delete activity with existing subscriptions.")
    activities_repo.delete(activity_id)
    try:
        from services import audit_service
        audit_service.record("activity.delete", target_type="activity", target_id=activity_id)
    except Exception:
        pass