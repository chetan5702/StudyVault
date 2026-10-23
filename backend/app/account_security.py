from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.email_delivery import DeliveryError, configured_provider
from app.models import AccountToken, User

EMAIL_VERIFICATION = "email_verification"
PASSWORD_RESET = "password_reset"
AccountEmailDelivery = tuple[str, str, str, str, str]


def account_token_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_account_token(
    db: Session, user: User, purpose: str, now: datetime
) -> tuple[AccountToken, str]:
    db.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user.id,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw_token = secrets.token_urlsafe(32)
    settings = get_settings()
    lifetime = (
        settings.email_verification_token_expire_minutes
        if purpose == EMAIL_VERIFICATION
        else settings.password_reset_token_expire_minutes
    )
    token = AccountToken(
        user_id=user.id,
        purpose=purpose,
        token_digest=account_token_digest(raw_token),
        expires_at=now + timedelta(minutes=lifetime),
        created_at=now,
    )
    db.add(token)
    db.flush()
    return token, raw_token


def account_token_on_cooldown(db: Session, user_id: str, purpose: str, now: datetime) -> bool:
    latest = (
        db.query(AccountToken)
        .filter(
            AccountToken.user_id == user_id,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
        )
        .order_by(AccountToken.created_at.desc())
        .first()
    )
    if latest is None:
        return False
    return (
        now - latest.created_at
    ).total_seconds() < get_settings().verification_resend_cooldown_seconds


def claim_account_token(
    db: Session, raw_token: str, purpose: str, now: datetime
) -> AccountToken | None:
    digest = account_token_digest(raw_token)
    token = (
        db.query(AccountToken)
        .filter(
            AccountToken.token_digest == digest,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
            AccountToken.expires_at > now,
        )
        .first()
    )
    if token is None:
        return None
    claimed = db.execute(
        update(AccountToken)
        .where(
            AccountToken.id == token.id,
            AccountToken.used_at.is_(None),
            AccountToken.expires_at > now,
        )
        .values(used_at=now)
    ).rowcount
    return token if claimed == 1 else None


def invalidate_other_account_tokens(
    db: Session, user_id: str, purpose: str, claimed_id: str, now: datetime
) -> None:
    db.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user_id,
            AccountToken.purpose == purpose,
            AccountToken.id != claimed_id,
            AccountToken.used_at.is_(None),
        )
        .values(used_at=now)
    )


def prepare_account_email(user: User, token: AccountToken, raw_token: str) -> AccountEmailDelivery:
    return user.email, user.full_name, token.purpose, token.id, raw_token


def send_account_email(
    recipient: str,
    full_name: str,
    purpose: str,
    token_id: str,
    raw_token: str,
) -> str:
    provider = configured_provider()
    if provider is None:
        raise DeliveryError("Email provider is not configured", retryable=False)

    settings = get_settings()
    route = "verify-email" if purpose == EMAIL_VERIFICATION else "reset-password"
    url = f"{settings.public_frontend_url.rstrip('/')}/{route}?{urlencode({'token': raw_token})}"
    if purpose == EMAIL_VERIFICATION:
        subject = "Verify your StudyVault email"
        body = (
            f"Hello {full_name},\n\n"
            f"Verify your StudyVault email address: {url}\n\n"
            "If you did not create this account, you can ignore this message."
        )
    else:
        subject = "Reset your StudyVault password"
        body = (
            f"Hello {full_name},\n\n"
            f"Choose a new StudyVault password: {url}\n\n"
            "If you did not request a password reset, you can ignore this message."
        )
    return provider.send(
        recipient=recipient,
        subject=subject,
        body=body,
        idempotency_key=f"studyvault-account-{purpose}-{token_id}",
    )
