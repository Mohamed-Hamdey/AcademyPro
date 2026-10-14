markdown
# License workflow

How to issue a license to a new customer.

## One-time setup (developer)

1. Install `cryptography`:
pip install cryptography

text

2. Generate the keypair (only once, ever):
python license/keys/generate_keypair.py

text

3. You now have:
- `license/keys/private_key.pem` — **SECRET**. Do not commit. Back up offline.
- `license/keys/public_key.pem` — safe to commit. The app uses it.

4. **Back up `private_key.pem`** to a USB drive, cloud storage, and a
physical printout. If you lose it you cannot issue any more licenses.
If it leaks, anyone can issue licenses for your app.

## Issuing a license

1. Customer launches the app for the first time. They see:
Your Machine ID: AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH
Send this to your provider to receive an activation code.

text

2. They send you the ID (WhatsApp, email, SMS — any channel).

3. On your dev machine:
python license/issue_license.py AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH

text

Optional: add a number of days as a second argument. Default is 3650 (10 years).
python license/issue_license.py AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH 365

text

4. The script produces a file like:
license_out/license_AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHH_2026-10-14.key

text

5. Email that file to the customer.

6. Customer clicks **Import License File** and picks the file. The app
validates and proceeds to login.

## Verifying an existing license

To check if a customer's machine is valid, ask them to open the app.
If the app launches to login without a license prompt, they're activated.

## Revoking a license

There's no active revocation mechanism in this version. Licenses expire
on their own date. To "revoke" before expiry, wait it out — the app
won't renew without a new file.

## What if the customer reinstalls Windows?

The Machine ID changes (it's derived from the OS MachineGuid + disk serial).
They'll need a new license. Send them a fresh one.

## What if the customer moves the app to a new PC?

Same — new machine, new ID, new license.

## What if the customer copies the app to another PC and shares the .key file?

The .key file has the original machine ID embedded. On the second PC,
the ID doesn't match and the app refuses to launch past the license
screen.

## Important — files to keep secret

- `license/keys/private_key.pem` — **NEVER** commit to git, **NEVER** ship in the app.
- `license_out/` — contains issued licenses with customer machine IDs.

Add to `.gitignore`:
license/keys/private_key.pem
license_out/