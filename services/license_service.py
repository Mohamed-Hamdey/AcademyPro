"""
License service — validates and stores the activation license.

Design:
  * Ed25519 signed license file, issued offline by the developer.
  * License is bound to a machine fingerprint derived from:
      - Windows MachineGuid (HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid)
      - Primary MAC address
      - C: volume serial number
    Combined and SHA-256 hashed, formatted as a friendly hex ID.
  * The license is validated on every launch:
      1. Signature valid (public key embedded in the app)
      2. machine_id matches this machine
      3. Not expired
  * If valid, the app proceeds. If not, only the License screen shows.

Files:
  %LOCALAPPDATA%\\AcademySystem\\license.key     the imported license JSON
  %LOCALAPPDATA%\\AcademySystem\\machine.id      cached machine fingerprint
"""

import os
import sys
import json
import base64
import hashlib
import subprocess
from dataclasses import dataclass
from datetime import date
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from paths import user_data_path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _license_path() -> str:
    return user_data_path("license.key", create_parent=True)


def _machine_id_cache_path() -> str:
    return user_data_path("machine.id", create_parent=True)


def _public_key_path() -> str:
    """Public key ships inside the app bundle."""
    from paths import bundled_path
    return bundled_path("license", "keys", "public_key.pem")


# ---------------------------------------------------------------------------
# Machine fingerprint
# ---------------------------------------------------------------------------

def get_machine_id() -> str:
    """
    Returns a stable fingerprint for this physical machine, or the cached
    value if we've computed it before.

    On Windows: hash(MachineGuid + first MAC + C: volume serial).
    On other platforms: falls back to a hash of platform + hostname + MAC.
    """
    # Cached value takes priority — never change it once assigned
    cache = _machine_id_cache_path()
    if os.path.exists(cache):
        try:
            with open(cache, "r", encoding="utf-8") as f:
                cached = f.read().strip()
            if cached:
                return cached
        except Exception:
            pass

    mid = _compute_machine_id()

    # Cache it — forever. If the machine's components change, the ID
    # would change too, and we don't want to invalidate licenses just
    # because someone added a second network card.
    try:
        with open(cache, "w", encoding="utf-8") as f:
            f.write(mid)
    except Exception:
        pass

    return mid


def _compute_machine_id() -> str:
    parts = []

    if sys.platform == "win32":
        parts.append(_windows_machine_guid() or "")
        parts.append(_primary_mac() or "")
        parts.append(_windows_volume_serial("C:") or "")
    else:
        import platform, uuid
        parts.append(platform.node() or "")
        parts.append(platform.system() or "")
        parts.append(_primary_mac() or "")

    raw = "|".join(parts).encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    hex_str = digest.hex().upper()[:32]

    # Format as AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH
    return "-".join(hex_str[i:i+4] for i in range(0, 32, 4))


def _windows_machine_guid() -> Optional[str]:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return value
    except Exception:
        return None


def _windows_volume_serial(drive: str) -> Optional[str]:
    try:
        # volume_serial via `vol` is unreliable across locales. Use ctypes.
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        root = drive + "\\"
        serial = wintypes.DWORD(0)
        max_component = wintypes.DWORD(0)
        flags = wintypes.DWORD(0)
        fs_name_buf = ctypes.create_unicode_buffer(256)

        ok = kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            None,
            0,
            ctypes.byref(serial),
            ctypes.byref(max_component),
            ctypes.byref(flags),
            fs_name_buf,
            256,
        )
        if not ok:
            return None
        return f"{serial.value:08X}"
    except Exception:
        return None


def _primary_mac() -> Optional[str]:
    try:
        import uuid
        mac = uuid.getnode()
        # getnode() can return a random number if MAC is unavailable — detect that
        # (multicast bit set means it's random)
        if (mac >> 40) & 1:
            return None
        return f"{mac:012X}"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# License data
# ---------------------------------------------------------------------------

@dataclass
class License:
    machine_id: str
    issued: str
    expires: str
    version: int


@dataclass
class LicenseStatus:
    valid: bool
    reason: str                # "" if valid, else human-readable
    license: Optional[License] = None
    machine_id: str = ""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def get_status() -> LicenseStatus:
    """
    Full check. Called at launch to decide whether to show the login or
    the license screen.
    """
    this_machine = get_machine_id()

    lic_path = _license_path()
    if not os.path.exists(lic_path):
        return LicenseStatus(
            valid=False, reason="no_license",
            machine_id=this_machine,
        )

    try:
        with open(lic_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return LicenseStatus(
            valid=False, reason="malformed",
            machine_id=this_machine,
        )

    # --- Signature check ---
    try:
        payload = data["payload"]
        signature = base64.b64decode(data["signature"])
    except (KeyError, ValueError):
        return LicenseStatus(
            valid=False, reason="malformed",
            machine_id=this_machine,
        )

    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

    if not _verify_signature(payload_bytes, signature):
        return LicenseStatus(
            valid=False, reason="bad_signature",
            machine_id=this_machine,
        )

    # --- Machine binding check ---
    lic_machine = (payload.get("machine_id") or "").strip().upper()
    if lic_machine != this_machine.upper():
        return LicenseStatus(
            valid=False, reason="wrong_machine",
            machine_id=this_machine,
        )

    # --- Expiry check ---
    try:
        expires = date.fromisoformat(payload.get("expires", ""))
    except ValueError:
        return LicenseStatus(
            valid=False, reason="malformed",
            machine_id=this_machine,
        )

    if date.today() > expires:
        return LicenseStatus(
            valid=False, reason="expired",
            license=License(
                machine_id=lic_machine,
                issued=payload.get("issued", ""),
                expires=payload.get("expires", ""),
                version=payload.get("version", 1),
            ),
            machine_id=this_machine,
        )

    # All good
    return LicenseStatus(
        valid=True, reason="",
        license=License(
            machine_id=lic_machine,
            issued=payload.get("issued", ""),
            expires=payload.get("expires", ""),
            version=payload.get("version", 1),
        ),
        machine_id=this_machine,
    )


def _verify_signature(payload_bytes: bytes, signature: bytes) -> bool:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        print("[license] cryptography not installed — cannot verify")
        return False

    pub_path = _public_key_path()
    if not os.path.exists(pub_path):
        print(f"[license] public key not found at {pub_path}")
        return False

    try:
        with open(pub_path, "rb") as f:
            public_key = serialization.load_pem_public_key(f.read())
        public_key.verify(signature, payload_bytes)
        return True
    except InvalidSignature:
        return False
    except Exception as e:
        print(f"[license] signature verification error: {e}")
        return False


# ---------------------------------------------------------------------------
# Import a license file
# ---------------------------------------------------------------------------

def import_license_file(source_path: str) -> LicenseStatus:
    """
    Copy a license file into the app data folder and validate it.

    Returns the resulting status. If valid, the license is now active.
    """
    if not os.path.exists(source_path):
        return LicenseStatus(
            valid=False, reason="not_found",
            machine_id=get_machine_id(),
        )

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            # Just to validate JSON parse before copying
            json.load(f)
    except Exception:
        return LicenseStatus(
            valid=False, reason="malformed",
            machine_id=get_machine_id(),
        )

    # Copy to the app data folder
    try:
        import shutil
        shutil.copy2(source_path, _license_path())
    except Exception:
        return LicenseStatus(
            valid=False, reason="copy_failed",
            machine_id=get_machine_id(),
        )

    # Validate now that it's in place
    return get_status()


# ---------------------------------------------------------------------------
# Human-readable reason messages
# ---------------------------------------------------------------------------

def reason_message(reason: str) -> str:
    """Return the translation key for a given reason code."""
    return {
        "no_license":    "license.reason.no_license",
        "malformed":     "license.reason.malformed",
        "bad_signature": "license.reason.bad_signature",
        "wrong_machine": "license.reason.wrong_machine",
        "expired":       "license.reason.expired",
        "not_found":     "license.reason.not_found",
        "copy_failed":   "license.reason.copy_failed",
    }.get(reason, "license.reason.unknown")