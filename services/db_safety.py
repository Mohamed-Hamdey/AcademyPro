"""
Database safety helpers: integrity check + pre-migration snapshots.

These are deliberately separate from services/backup_service.py:

  * backup_service handles *user-facing* scheduled backups (auto on
    start/close, manual via menu) into the user-visible backups folder.

  * db_safety handles *internal* one-shot snapshots taken immediately
    before a migration runs, written next to the DB as
    `academy.db.bak.pre-migration-<N>`. They're short-lived and are
    rotated (only the last few are kept).

  * Also provides the startup integrity check.
"""

import os
import shutil
import sqlite3
import logging
from typing import Optional

from paths import AppPaths


log = logging.getLogger(__name__)


MAX_PRE_MIGRATION_SNAPSHOTS = 3


# ---------------------------------------------------------------------------
# Integrity check
# ---------------------------------------------------------------------------

def check_integrity(db_path: str = None) -> tuple[bool, str]:
    """
    Run PRAGMA integrity_check on the DB.

    Returns (ok, message). `ok` is True if the DB opens and passes;
    False otherwise. `message` is "" on success, a short description on
    failure.
    """
    if db_path is None:
        db_path = AppPaths.database()

    if not os.path.exists(db_path):
        return True, ""   # fresh install — nothing to check

    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("PRAGMA integrity_check;").fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        return False, str(e)
    except Exception as e:
        return False, f"unexpected error: {e}"

    if row is None:
        return True, ""

    # integrity_check returns a single row "ok" on success,
    # or a series of rows describing the corruption on failure.
    result = row[0] if isinstance(row, (tuple, list)) else row
    if result == "ok":
        return True, ""
    return False, str(result)


# ---------------------------------------------------------------------------
# Pre-migration snapshots
# ---------------------------------------------------------------------------

def _snapshot_dir() -> str:
    return AppPaths.data_root()


def _snapshot_path(version: int) -> str:
    return os.path.join(
        _snapshot_dir(), f"academy.db.bak.pre-migration-{version:03d}"
    )


def take_pre_migration_snapshot(next_version: int) -> Optional[str]:
    """
    Copy the DB to a per-version snapshot file before a migration runs.

    Returns the snapshot path, or None if the DB didn't exist yet
    (fresh install — no snapshot needed).
    """
    try:
        src = AppPaths.database()
        if not os.path.exists(src):
            return None

        dest = _snapshot_path(next_version)
        # Overwrite any stale snapshot with the same version — the
        # current state is the one that matters.
        shutil.copy2(src, dest)
        log.info("Pre-migration snapshot v%03d → %s", next_version, dest)
        _prune_snapshots()
        return dest
    except Exception as e:
        log.exception("take_pre_migration_snapshot failed: %s", e)
        return None


def restore_pre_migration_snapshot(version: int) -> bool:
    """
    Copy the snapshot for `version` back over the live DB.
    Used only when a migration has failed.
    """
    try:
        src = _snapshot_path(version)
        if not os.path.exists(src):
            log.error("No pre-migration snapshot to restore for v%03d", version)
            return False

        dest = AppPaths.database()
        shutil.copy2(src, dest)
        log.warning("Restored pre-migration snapshot v%03d over live DB",
                    version)
        return True
    except Exception as e:
        log.exception("restore_pre_migration_snapshot failed: %s", e)
        return False


def _prune_snapshots() -> None:
    """Keep only the newest MAX_PRE_MIGRATION_SNAPSHOTS snapshot files."""
    try:
        d = _snapshot_dir()
        if not os.path.isdir(d):
            return
        files = [
            os.path.join(d, n)
            for n in os.listdir(d)
            if n.startswith("academy.db.bak.pre-migration-")
        ]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for old in files[MAX_PRE_MIGRATION_SNAPSHOTS:]:
            try:
                os.remove(old)
                log.info("Pruned old snapshot: %s", old)
            except OSError:
                pass
    except Exception as e:
        log.warning("prune snapshots failed: %s", e)