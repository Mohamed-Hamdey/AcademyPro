"""
Authentication — password hashing, login, user management.

Uses PBKDF2-HMAC-SHA256 from the Python standard library. No external
crypto dependency. Iteration count is high enough to make offline
brute-forcing impractical for a small user base.
"""

import os
import sys
import hmac
import hashlib
import secrets

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from repositories import users_repo
from repositories.users_repo import User


# ---------------------------------------------------------------------------
# Password hashing — PBKDF2-HMAC-SHA256
# ---------------------------------------------------------------------------

_ITERATIONS = 260_000       # ~2020s guidance for PBKDF2-SHA256
_SALT_BYTES = 16
_HASH_BYTES = 32
_ALGORITHM = "pbkdf2_sha256"


def hash_password(plain: str) -> str:
    """
    Hash a password. Returns a self-describing string:
        pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    if not plain:
        raise ValueError("Password cannot be empty")
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        plain.encode("utf-8"),
        salt,
        _ITERATIONS,
        dklen=_HASH_BYTES,
    )
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison of a plain password against a stored hash."""
    if not hashed or not plain:
        return False
    try:
        algorithm, iterations_str, salt_hex, hash_hex = hashed.split("$", 3)
    except ValueError:
        return False
    if algorithm != _ALGORITHM:
        return False

    try:
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(candidate, expected)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

# The migration seeded `manager` with this placeholder string.
_PLACEHOLDER_HASH = "PLACEHOLDER_TO_BE_REPLACED"

# Default password used when the placeholder hash is still in place. The
# user must change it immediately after first login.
DEFAULT_MANAGER_PASSWORD = "admin"


def needs_bootstrap(username: str) -> bool:
    """
    True if the given username exists but still has the placeholder hash —
    meaning we need to accept the default password and force a change.
    """
    user = users_repo.get_by_username(username)
    return user is not None and user.password_hash == _PLACEHOLDER_HASH


def bootstrap_password(username: str, new_password: str) -> None:
    """Replace the placeholder hash with a real one for a bootstrapped user."""
    user = users_repo.get_by_username(username)
    if user is None:
        return
    users_repo.set_password(user.user_id, hash_password(new_password))


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginResult:
    """Result of a login attempt. Distinguishes failure modes so the UI can
    show a helpful message."""
    def __init__(self, user, status, message=""):
        self.user = user           # User | None
        self.status = status       # "ok" | "bad_credentials" | "inactive" |
                                   # "bootstrap"
        self.message = message

    @property
    def ok(self):
        return self.status == "ok"


def login(username: str, password: str) -> LoginResult:
    """
    Try to log a user in.
    Returns a LoginResult. On success, `user` is populated and
    `last_login` has been touched.
    """
    username = (username or "").strip()
    if not username or not password:
        return LoginResult(None, "bad_credentials")

    user = users_repo.get_by_username(username)
    if user is None:
        return LoginResult(None, "bad_credentials")

    # First-run bootstrap: the placeholder hash accepts the default password.
    if user.password_hash == _PLACEHOLDER_HASH:
        if password == DEFAULT_MANAGER_PASSWORD:
            # Return a bootstrap signal so the UI forces a password change.
            return LoginResult(user, "bootstrap")
        return LoginResult(None, "bad_credentials")

    if not verify_password(password, user.password_hash):
        return LoginResult(None, "bad_credentials")

    if not user.active:
        return LoginResult(None, "inactive")

    users_repo.touch_last_login(user.user_id)
    return LoginResult(user, "ok")


# ---------------------------------------------------------------------------
# User management (manager-only actions)
# ---------------------------------------------------------------------------

def create_user(username: str, display_name: str, password: str, role: str) -> int:
    """
    Create a new user. Validates:
      * username is non-empty and unique
      * display_name is non-empty
      * password is non-empty
      * role is one of 'manager' | 'receptionist'
    Raises ValueError on validation failure.
    """
    username = (username or "").strip()
    display_name = (display_name or "").strip()
    if not username:
        raise ValueError("Username is required")
    if not display_name:
        raise ValueError("Display name is required")
    if not password:
        raise ValueError("Password is required")
    if role not in ("manager", "receptionist"):
        raise ValueError("Invalid role")

    existing = users_repo.get_by_username(username)
    if existing is not None:
        raise ValueError(f"Username '{username}' is already taken")

    return users_repo.create(
        username=username,
        display_name=display_name,
        password_hash=hash_password(password),
        role=role,
    )


def change_password(user_id: int, new_password: str) -> None:
    if not new_password:
        raise ValueError("Password cannot be empty")
    users_repo.set_password(user_id, hash_password(new_password))