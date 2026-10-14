"""
Generate an Ed25519 keypair for licensing.

Run ONCE on your dev machine:

    python license/keys/generate_keypair.py

Creates:
    license/keys/private_key.pem   ← KEEP SECRET. Do NOT ship. Backup offline.
    license/keys/public_key.pem    ← Embedded in the app. Safe to ship.

If either file already exists, the script refuses to overwrite — delete them
manually if you really want to regenerate (which will invalidate every
existing license).
"""

import os
import sys

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    print("ERROR: `cryptography` is not installed.")
    print("Run:  pip install cryptography")
    sys.exit(1)


OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PRIVATE_PATH = os.path.join(OUT_DIR, "private_key.pem")
PUBLIC_PATH = os.path.join(OUT_DIR, "public_key.pem")


def main():
    if os.path.exists(PRIVATE_PATH) or os.path.exists(PUBLIC_PATH):
        print("Keypair already exists:")
        if os.path.exists(PRIVATE_PATH):
            print(f"  {PRIVATE_PATH}")
        if os.path.exists(PUBLIC_PATH):
            print(f"  {PUBLIC_PATH}")
        print("\nRefusing to overwrite. Delete both files to regenerate.")
        print("WARNING: regenerating will invalidate every existing license.")
        return

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Private key — PEM, unencrypted (keep offline + secure)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(PRIVATE_PATH, "wb") as f:
        f.write(priv_pem)

    # Public key — PEM, embedded in the app
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(PUBLIC_PATH, "wb") as f:
        f.write(pub_pem)

    print("Keypair generated:")
    print(f"  private: {PRIVATE_PATH}")
    print(f"  public:  {PUBLIC_PATH}")
    print()
    print("NEXT STEPS:")
    print("  1. BACK UP private_key.pem somewhere safe (USB drive, offline).")
    print("     If you lose it, you cannot issue any new licenses.")
    print("  2. NEVER commit private_key.pem to git.")
    print("  3. Commit public_key.pem — the app embeds it.")


if __name__ == "__main__":
    main()