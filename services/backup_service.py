"""
Database backup and restore.

Backups live in %LOCALAPPDATA%\\AcademySystem\\backups\\ as timestamped
SQLite copies. Two kinds:

  * auto   — created on app start (and eventually on app close)
  * manual — created by the user via the "Backup now" menu item

Both are just file copies of academy.db — SQLite's own transaction log
ensures a consistent snapshot as long as no writer is mid-transaction,
which is the case when we run on startup before the UI is doing work.

Naming convention:
    academy_2026-10-16_0153_auto.db
    academy_2026-10-16_1042_manual.db

Restore is destructive. The caller MUST confirm with the user and MUST
restart the app after a restore, because the running process holds a
cached view of the old database.
"""

import os
import shutil
import sqlite3
import logging
from datetime import datetime
from typing import Optional

from paths import AppPaths


log = logging.getLogger(__name__)


# Auto-backups are pruned; manual ones are kept indefinitely.
DEFAULT_KEEP_AUTO = 14


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _backups_dir() -> str:
    return AppPaths.backups_dir()


def _db_path() -> str:
    return AppPaths.database()


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M")


def _make_name(label: str) -> str:
    return f"academy_{_timestamp()}_{label}.db"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_backup(label: str = "auto") -> Optional[str]:
    """
    Copy the current database to a timestamped file in the backups folder.

    Returns the absolute path of the created backup, or None on failure.
    Never raises — a backup failure must not stop the app.
    """
    try:
        src = _db_path()
        if not os.path.exists(src):
            log.warning("create_backup: database file not found at %s", src)
            return None

        # Ensure the folder exists.
        os.makedirs(_backups_dir(), exist_ok=True)

        # Build a name; if two backups land in the same minute with the
        # same label, add a counter suffix to avoid clobbering.
        base = _make_name(label)
        dest = os.path.join(_backups_dir(), base)
        counter = 1
        while os.path.exists(dest):
            stem, ext = os.path.splitext(base)
            dest = os.path.join(_backups_dir(), f"{stem}_{counter}{ext}")
            counter += 1

        # Quick integrity check on the source before copying — cheap, and
        # means we don't propagate a corrupt file into the backups folder.
        try:
            conn = sqlite3.connect(src)
            try:
                conn.execute("PRAGMA schema_version;").fetchone()
            finally:
                conn.close()
        except sqlite3.DatabaseError as e:
            log.error("create_backup: source db failed integrity check: %s", e)
            return None

        try:
            shutil.copy2(src, dest)
        except Exception:
            # Copy failed (disk full, permission, network interruption).
            # Clean up the partial file so it doesn't appear in the
            # backup list as a corrupt entry.
            try:
                if os.path.exists(dest):
                    os.remove(dest)
            except OSError:
                pass
            raise

        # Sanity check: the destination should have the same size as
        # the source. If not, treat as a failed backup.
        try:
            if os.path.getsize(dest) != os.path.getsize(src):
                raise IOError(
                    f"Backup size mismatch: {os.path.getsize(dest)} "
                    f"vs {os.path.getsize(src)}"
                )
        except OSError:
            # If we can't stat it, that's a failure too.
            try:
                os.remove(dest)
            except OSError:
                pass
            raise

        log.info("Backup created: %s (%d bytes)", dest, os.path.getsize(dest))
        return dest

    except Exception as e:
        log.exception("create_backup failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def list_backups() -> list[dict]:
    """
    Return available backups, newest first. Each entry:
        {
            "path":  str,
            "name":  str,
            "size":  int,          # bytes
            "mtime": float,        # epoch seconds
            "label": "auto"|"manual"|"pre-restore"|"unknown",
        }
    """
    result = []
    d = _backups_dir()
    if not os.path.isdir(d):
        return result

    for name in os.listdir(d):
        if not name.endswith(".db"):
            continue
        full = os.path.join(d, name)
        if not os.path.isfile(full):
            continue
        try:
            st = os.stat(full)
        except OSError:
            continue
        result.append({
            "path":  full,
            "name":  name,
            "size":  st.st_size,
            "mtime": st.st_mtime,
            "label": _label_from_name(name),
        })

    result.sort(key=lambda r: r["mtime"], reverse=True)
    return result


def _label_from_name(name: str) -> str:
    """Parse the trailing label from academy_<date>_<time>_<label>.db."""
    try:
        stem = name[:-3]  # strip ".db"
        parts = stem.split("_")
        if len(parts) >= 4:
            return "_".join(parts[3:])   # handles pre-restore, etc.
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# Prune
# ---------------------------------------------------------------------------

def prune_auto_backups(keep: int = DEFAULT_KEEP_AUTO) -> int:
    """
    Delete the oldest auto backups beyond `keep`. Never touches manual
    or pre-restore backups.

    Returns the number of files deleted.
    """
    backups = [b for b in list_backups() if b["label"] == "auto"]
    # list_backups already sorts newest-first.
    to_delete = backups[keep:]
    deleted = 0
    for b in to_delete:
        try:
            os.remove(b["path"])
            log.info("Pruned old auto backup: %s", b["name"])
            deleted += 1
        except OSError as e:
            log.warning("prune: failed to remove %s: %s", b["path"], e)
    return deleted


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def verify_backup(path: str) -> bool:
    """
    Return True if `path` is a readable SQLite file with a valid header.
    Doesn't check the schema — only that it opens and answers a query.
    """
    if not path or not os.path.isfile(path):
        return False
    try:
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA schema_version;").fetchone()
        finally:
            conn.close()
        return True
    except sqlite3.DatabaseError as e:
        log.warning("verify_backup: %s failed: %s", path, e)
        return False


def restore_backup(backup_path: str) -> bool:
    """
    Replace the live database with `backup_path`.

    Steps:
      1. Verify the chosen backup opens as SQLite.
      2. Take a pre-restore safety copy of the current DB (if it exists).
      3. Copy the backup over the live database file.

    The caller MUST:
      - Confirm with the user before calling this.
      - Restart the app after this succeeds (the running process holds
        stale data in memory).

    Returns True on success, False otherwise. Never raises.
    """
    try:
        if not verify_backup(backup_path):
            log.error("restore_backup: chosen file is not a valid SQLite db: %s",
                      backup_path)
            return False

        live = _db_path()

        # Safety copy first — if this fails, do not proceed.
        if os.path.exists(live):
            safety = os.path.join(
                _backups_dir(), _make_name("pre-restore")
            )
            try:
                shutil.copy2(live, safety)
                log.info("Pre-restore safety copy: %s", safety)
            except Exception as e:
                log.exception("restore_backup: could not make safety copy: %s", e)
                return False

        # Replace.
        try:
            shutil.copy2(backup_path, live)
        except Exception as e:
            log.exception("restore_backup: copy failed: %s", e)
            return False

        # Post-copy verification — the live file must open.
        if not verify_backup(live):
            log.error("restore_backup: live db failed post-restore check")
            return False

        log.info("Restore complete from %s", backup_path)
        return True

    except Exception as e:
        log.exception("restore_backup failed: %s", e)
        return False