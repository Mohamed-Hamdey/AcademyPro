"""
Global application state.

Holds the currently logged-in user and provides simple role-gate helpers.
Imported as a singleton:

    from app_state import app
    if app.is_manager():
        ...
"""

from __future__ import annotations

from typing import Optional

from repositories.users_repo import User


class AppState:
    def __init__(self):
        self.current_user: Optional[User] = None

    # ---- current user ----

    def set_user(self, user: Optional[User]) -> None:
        self.current_user = user

    def clear(self) -> None:
        self.current_user = None

    @property
    def user(self) -> Optional[User]:
        return self.current_user

    @property
    def is_logged_in(self) -> bool:
        return self.current_user is not None

    # ---- role helpers ----

    @property
    def role(self) -> str:
        return self.current_user.role if self.current_user else "guest"

    def is_manager(self) -> bool:
        return self.role == "manager"

    def is_receptionist(self) -> bool:
        return self.role == "receptionist"

    def recorded_by(self) -> str:
        """The username to store on actions taken right now."""
        return self.current_user.username if self.current_user else "unknown"

    # ---- permission gates ----
    #
    # Central place to declare what each role can do. Screens should ask
    # `app.can("...")` rather than checking role strings directly.

    PERMISSIONS = {
        "checkin":          {"manager", "receptionist"},
        "players.view":     {"manager", "receptionist"},
        "players.edit":     {"manager", "receptionist"},
        "players.add":      {"manager", "receptionist"},
        "subscription.manage": {"manager", "receptionist"},
        "attendance.undo":  {"manager"},
        "activities.manage": {"manager"},
        "reports.view":     {"manager"},
        "financials.view":  {"manager"},
        "expenses.manage":  {"manager"},
        "users.manage":     {"manager"},
        "audit.view":       {"manager"},
        "settings.manage":  {"manager"},
    }

    def can(self, action: str) -> bool:
        allowed_roles = self.PERMISSIONS.get(action)
        if allowed_roles is None:
            return False
        return self.role in allowed_roles


# Singleton
app = AppState()