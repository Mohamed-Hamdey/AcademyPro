"""
Issue a license file for a customer's machine.

Usage:
    python license/issue_license.py <MACHINE_ID> [days]

    MACHINE_ID   the ID the customer sent you (e.g. "A1-B2-C3-...")
    days         optional license duration in days (default: 3650 = 10 years)

Produces:
    license_out/license_<MACHINE_ID>_<YYYY-MM-DD>.key

Email that file back to the customer. They import it in the app.
"""

import os
import sys
import json
import base64
from datetime import date, timedelta

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    print("ERROR: `cryptography` is not installed.")
    print("Run:  pip install cryptography")
    sys.exit(1)


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KEYS_DIR = os.path.join(PROJECT_ROOT, "license", "keys")
PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, "private_key.pem")
OUT_DIR = os.path.join(PROJECT_ROOT, "license_out")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    machine_id = sys.argv[1].strip().upper()
    if not machine_id:
        print("ERROR: empty machine ID")
        sys.exit(1)

    days = int(sys.argv[2]) if len(sys.argv) > 2 else 3650

    if not os.path.exists(PRIVATE_KEY_PATH):
        print(f"ERROR: private key not found at {PRIVATE_KEY_PATH}")
        print("Run first:  python license/keys/generate_keypair.py")
        sys.exit(1)

    # Load private key
    with open(PRIVATE_KEY_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(), password=None,
        )

    issued = date.today()
    expires = issued + timedelta(days=days)

    # The payload we sign — all fields the app validates
    payload = {
        "machine_id": machine_id,
        "issued":     issued.isoformat(),
        "expires":    expires.isoformat(),
        "version":    1,
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

    signature = private_key.sign(payload_bytes)

    # Write the license file: payload + base64(signature)
    license_data = {
        "payload":   payload,
        "signature": base64.b64encode(signature).decode("ascii"),
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    filename = f"license_{machine_id.replace('-', '')}_{issued.isoformat()}.key"
    out_path = os.path.join(OUT_DIR, filename)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(license_data, f, indent=2, ensure_ascii=False)

    print("License issued:")
    print(f"  file:     {out_path}")
    print(f"  machine:  {machine_id}")
    print(f"  issued:   {issued}")
    print(f"  expires:  {expires}  ({days} days)")
    print()
    print("Email this file to the customer along with instructions:")
    print("  1. Open the Academy System app.")
    print("  2. Click 'Import license file'.")
    print("  3. Pick the file you received.")


if __name__ == "__main__":
    main()