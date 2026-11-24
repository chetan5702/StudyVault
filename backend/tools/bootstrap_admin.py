"""Operator-only initial administrator promotion (no public bootstrap endpoint).

Usage, from the backend directory and with the intended database configured:
    python -m tools.bootstrap_admin --email approved-admin@suh.edu.in --confirm

Promote only an existing, verified and active account whose identity and
authorization to administer StudyVault have been confirmed out-of-band.
This tool never creates accounts and is intentionally non-automatic.
"""

import argparse

from app.database import SessionLocal
from app.datetime_type import utcnow
from app.models import StaffAuditEvent, StaffRole, User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        raise SystemExit("No changes made. Specify --confirm after verifying authorization.")
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == args.email.strip().lower()).one_or_none()
        if user is None or not user.is_active or user.email_verified_at is None:
            raise SystemExit("No eligible verified and active account found.")
        if db.get(StaffRole, user.id) is not None:
            raise SystemExit("Account already has a staff role; no changes made.")
        db.add(StaffRole(user_id=user.id, role="admin", granted_at=utcnow()))
        db.add(StaffAuditEvent(
            actor_id=user.id, action="admin.bootstrapped", entity_id=user.id
        ))
        db.commit()
        print("Admin bootstrap successful for the reviewed account.")


if __name__ == "__main__":
    main()
