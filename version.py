"""
Single source of truth for the application version.

Everywhere the version is needed — the About dialog, the installer
filename, the window title suffix, the diagnostics block — reads from
here. Change this one string to bump the version.

Semantic versioning:
    MAJOR.MINOR.PATCH

    MAJOR — breaking changes, DB schema changes requiring migration
    MINOR — new features, backward compatible
    PATCH — bug fixes only
"""

__version__ = "1.0.0"

# Display name shown in the About dialog. Keep this short.
APP_NAME = "Academy Membership System"