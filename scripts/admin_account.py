#!/usr/bin/env python3
"""
Owner-run admin account recovery for the PRODUCTION database (aayna_prod).

    python scripts/admin_account.py status       --env-file .env.prod-import
    python scripts/admin_account.py set-password --env-file .env.prod-import --email you@example.com

status (read-only) lists admin accounts: role, status, masked email.
set-password asks for the new password twice WITHOUT echoing it (getpass),
requires at least 12 characters, stores only a bcrypt hash, and signs out every
existing session of that account (session_version + 1). It changes nothing else
and never creates an account. The password is never printed, logged or stored in
plain text. Run it yourself on your own computer - it is the deliberate,
owner-authorized replacement for the old "overwrite on startup" behaviour.
"""
import argparse
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prod_catalogue_import import Stop, load_env_file, check_target, redact, sync_db, out  # noqa: E402
from prod_db_ops import mask_email  # noqa: E402

MIN_LEN = 12
ADMIN_ROLES = ["super_admin", "admin", "order_manager", "product_manager"]


def status(db):
    for u in db.users.find({"role": {"$in": ADMIN_ROLES}}, {"_id": 0, "password_hash": 0}):
        out(f"  {mask_email(u.get('email'))}  role={u.get('role')}  status={u.get('status')}  "
            f"sessions_reset={int(u.get('session_version', 0) or 0)}")


def set_password(db, email):
    import bcrypt
    email = (email or "").strip().lower()
    user = db.users.find_one({"email": email}, {"_id": 0, "id": 1, "role": 1, "status": 1})
    if not user:
        raise Stop("no account with that email (nothing changed)")
    if user.get("role") not in ADMIN_ROLES:
        raise Stop("that account is not an admin account (nothing changed)")
    pw1 = getpass.getpass("New password (min 12 characters, not shown): ")
    pw2 = getpass.getpass("Repeat new password: ")
    if pw1 != pw2:
        raise Stop("passwords do not match (nothing changed)")
    if len(pw1) < MIN_LEN:
        raise Stop(f"password must be at least {MIN_LEN} characters (nothing changed)")
    hashed = bcrypt.hashpw(pw1.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    res = db.users.update_one({"email": email}, {"$set": {"password_hash": hashed,
                                                          "updated_at": datetime.now(timezone.utc).isoformat()},
                                                 "$inc": {"session_version": 1}})
    if res.modified_count != 1:
        raise Stop("update failed (nothing changed)")
    out(f"Password updated for {mask_email(email)} ({user.get('role')}). All previous sessions are signed out.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["status", "set-password"])
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--email")
    a = ap.parse_args(argv)
    vals = {}
    try:
        vals = load_env_file(a.env_file)
        host = check_target(vals)
        client, db = sync_db(vals)
        try:
            db.command("ping")
            out(f"Target: {host} / {vals['DB_NAME']}")
            if a.cmd == "status":
                status(db)
            else:
                if not a.email:
                    a.email = input("Admin email: ")
                set_password(db, a.email)
        finally:
            client.close()
    except Stop as exc:
        out(f"\nSTOPPED: {redact(exc, vals)}")
        return 2
    except Exception as exc:  # noqa: BLE001
        out(f"\nERROR ({type(exc).__name__}): {redact(exc, vals)}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
