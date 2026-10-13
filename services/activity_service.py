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


def get_localized_name(activity: Activity) -> str:
    """Pick the Arabic or English name based on the current language."""
    if i18n.current_language() == "ar":
        return activity.name_ar or activity.name_en
    return activity.name_en or activity.name_ar


def create(name_en: str, name_ar: str, default_days: list[str],
           color: str = None) -> int:
    """
    Create a new activity. Raises ValueError on validation failure.
    """
    name_en = (name_en or "").strip()
    name_ar = (name_ar or "").strip()
    default_days = [d for d in (default_days or []) if d]

    if not name_en:
        raise ValueError("English name is required")
    if not name_ar:
        raise ValueError("Arabic name is required")
    if not default_days:
        raise ValueError("At least one training day is required")

    if activities_repo.name_exists(name_en):
        raise ValueError(f"An activity named '{name_en}' already exists")

    activity = Activity(
        activity_id=None,
        name_en=name_en,
        name_ar=name_ar,
        default_days=default_days,
        color=color,
        active=True,
    )
    return activities_repo.create(activity)


def update(activity_id: int, name_en: str, name_ar: str,
           default_days: list[str], color: str = None) -> None:
    """Update an existing activity. Raises ValueError on validation failure."""
    name_en = (name_en or "").strip()
    name_ar = (name_ar or "").strip()
    default_days = [d for d in (default_days or []) if d]

    if not name_en:
        raise ValueError("English name is required")
    if not name_ar:
        raise ValueError("Arabic name is required")
    if not default_days:
        raise ValueError("At least one training day is required")

    if activities_repo.name_exists(name_en, exclude_id=activity_id):
        raise ValueError(f"An activity named '{name_en}' already exists")

    existing = activities_repo.get_by_id(activity_id)
    if existing is None:
        raise ValueError("Activity not found")

    existing.name_en = name_en
    existing.name_ar = name_ar
    existing.default_days = default_days
    existing.color = color
    activities_repo.update(existing)


def deactivate(activity_id: int) -> None:
    """
    Soft-delete: sets active = False. Existing subscriptions keep working;
    the activity is just hidden from new-subscription pickers.
    """
    activities_repo.set_active(activity_id, False)


def reactivate(activity_id: int) -> None:
    activities_repo.set_active(activity_id, True)


def count_references(activity_id: int) -> int:
    """How many subscriptions reference this activity (for the delete
    confirmation message)."""
    return activities_repo.count_active_subscriptions(activity_id)