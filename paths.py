"""
Path resolution for the app.

Two categories of files:

  * BUNDLED, read-only — config, translations, logo, schema. These ship
    inside the .exe (or live in the project folder in source mode) and are
    never written to.

  * USER DATA, writable — the SQLite database, generated QR codes, and
    player photos. These must live OUTSIDE the bundle so they survive app
    updates and aren't wiped when the temp folder is cleaned up.

Usage — prefer the named classmethods on AppPaths:

    from paths import AppPaths

    cfg          = AppPaths.config_file()
    schema       = AppPaths.schema_file()
    translations = AppPaths.translations_dir()
    logo         = AppPaths.logo_file()
    db           = AppPaths.database()
    qr_folder    = AppPaths.qr_codes_dir()
    photo_folder = AppPaths.photos_dir()
    logs         = AppPaths.logs_dir()
    backups      = AppPaths.backups_dir()

The lower-level functions (bundled_path, user_data_path, user_data_dir,
user_data_root, project_root) are still exported for cases where a path
isn't covered by a named method. Prefer AppPaths when possible.
"""

import os
import sys


# ---------------------------------------------------------------------------
# Low-level path resolution
# ---------------------------------------------------------------------------

def bundled_path(*parts: str) -> str:
    """
    Absolute path to a read-only file that ships WITH the app.

    In a frozen build, files are unpacked under sys._MEIPASS.
    In source mode, they live relative to this file (the project root).
    """
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def project_root() -> str:
    """Root of the source tree (source mode) or temp bundle (frozen)."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


APP_DATA_DIRNAME = "AcademySystem"


def user_data_root() -> str:
    """
    Writable data root:
      Windows:  %LOCALAPPDATA%\\AcademySystem\\
      macOS:    ~/Library/Application Support/AcademySystem/
      Linux:    ~/.local/share/AcademySystem/
      Fallback: <project root>/data/
    """
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return os.path.join(local_appdata, APP_DATA_DIRNAME)

    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~"), "Library", "Application Support", APP_DATA_DIRNAME
        )

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return os.path.join(xdg, APP_DATA_DIRNAME)
    home = os.path.expanduser("~")
    if home and home != "~":
        return os.path.join(home, ".local", "share", APP_DATA_DIRNAME)

    return os.path.join(project_root(), "data")


def user_data_path(*parts: str, create_parent: bool = True) -> str:
    """Absolute path to a writable file under user_data_root()."""
    full = os.path.join(user_data_root(), *parts)
    if create_parent:
        parent = os.path.dirname(full)
        if parent:
            os.makedirs(parent, exist_ok=True)
    return full


def user_data_dir(*parts: str) -> str:
    """Absolute path to a writable directory under user_data_root().
    Creates the directory if it doesn't exist."""
    full = os.path.join(user_data_root(), *parts)
    os.makedirs(full, exist_ok=True)
    return full


# ---------------------------------------------------------------------------
# Named paths — use these instead of building paths inline
# ---------------------------------------------------------------------------

class AppPaths:
    """
    Every file path the app knows about, in one place. If you need a path
    that isn't here, add a classmethod rather than building it inline
    somewhere else.
    """

    # ----- Bundled (read-only) -----

    @classmethod
    def config_file(cls) -> str:
        return bundled_path("config", "academy_config.json")

    @classmethod
    def translations_dir(cls) -> str:
        return bundled_path("translations")

    @classmethod
    def schema_file(cls) -> str:
        return bundled_path("db", "schema.sql")

    @classmethod
    def logo_file(cls) -> str:
        return bundled_path("assets", "logo", "logo.png")

    # ----- User data (writable) -----

    @classmethod
    def data_root(cls) -> str:
        return user_data_root()

    @classmethod
    def database(cls) -> str:
        return user_data_path("academy.db")
    
    @classmethod
    def logs_dir(cls) -> str:
        """Directory for rotating log files. Created if it doesn't exist."""
        return user_data_dir("logs")

    @classmethod
    def backups_dir(cls) -> str:
        """Directory for automatic and manual database backups."""
        return user_data_dir("backups")

    @classmethod
    def qr_codes_dir(cls) -> str:
        return user_data_dir("assets", "qr_codes")

    @classmethod
    def photos_dir(cls) -> str:
        return user_data_dir("assets", "photos")