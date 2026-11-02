from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import and_, case, delete, or_, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.account_security import (
    EMAIL_VERIFICATION,
    PASSWORD_RESET,
    account_token_on_cooldown,
    claim_account_token,
    invalidate_other_account_tokens,
    issue_account_token,
    prepare_account_email,
    send_account_email,
)
from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.datetime_type import utcnow
from app.email_delivery import DeliveryError
from app.models import LoginAttempt, Profile, User, UserStorageUsage
from app.public_limits import login_limit, recovery_limit, register_limit, token_limit
from app.schemas import (
    AccountTokenRequest,
    EmailRequest,
    MessageOut,
    PasswordResetConfirm,
    TokenOut,
    UserLogin,
    UserRegister,
)
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])
settings = get_settings()
logger = logging.getLogger(__name__)

VERIFICATION_REQUEST_MESSAGE = (
    "If an unverified account exists for that email, a verification message has been sent."
)
RESET_REQUEST_MESSAGE = (
    "If an account exists for that email, password reset instructions have been sent."
)


def deliver_account_email(delivery: tuple[str, str, str, str, str], failure_message: str) -> None:
    try:
        send_account_email(*delivery)
    except DeliveryError:
        logger.warning(failure_message, exc_info=True)


def token_response(user: User) -> TokenOut:
    token = create_access_token(
        str(user.id),
        user.email,
        user.full_name,
        token_version=user.token_version,
    )
    return TokenOut(
        access_token=token,
        user={"id": user.id, "email": user.email, "full_name": user.full_name},
    )


def verification_required_response(user: User) -> TokenOut:
    return TokenOut(
        access_token=None,
        user={"id": user.id, "email": user.email, "full_name": user.full_name},
        verification_required=True,
    )


def login_identifier_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def active_login_lock(db: Session, identifier_hash: str, now: datetime) -> LoginAttempt | None:
    attempt = db.get(LoginAttempt, identifier_hash)
    if attempt is not None and attempt.locked_until is not None and attempt.locked_until > now:
        return attempt
    return None


def retry_after_seconds(attempt: LoginAttempt, now: datetime) -> int:
    return max(1, math.ceil((attempt.locked_until - now).total_seconds()))


def insert_login_attempt_if_missing(db: Session, identifier_hash: str, now: datetime) -> None:
    values = {
        "identifier_hash": identifier_hash,
        "failed_attempts": 0,
        "window_started_at": now,
        "locked_until": None,
        "updated_at": now,
    }
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        statement = sqlite_insert(LoginAttempt).values(**values).on_conflict_do_nothing()
        db.execute(statement)
    elif dialect == "postgresql":
        statement = postgresql_insert(LoginAttempt).values(**values).on_conflict_do_nothing()
        db.execute(statement)
    elif db.get(LoginAttempt, identifier_hash) is None:
        db.add(LoginAttempt(**values))
        db.flush()


def record_login_failure(db: Session, identifier_hash: str, now: datetime) -> None:
    retention_seconds = (
        max(
            settings.login_failure_window_seconds,
            settings.login_lockout_seconds,
        )
        * 2
    )
    db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.updated_at < now - timedelta(seconds=retention_seconds)
        )
    )
    insert_login_attempt_if_missing(db, identifier_hash, now)

    window_cutoff = now - timedelta(seconds=settings.login_failure_window_seconds)
    lock_until = now + timedelta(seconds=settings.login_lockout_seconds)
    expired = or_(
        LoginAttempt.window_started_at <= window_cutoff,
        and_(LoginAttempt.locked_until.is_not(None), LoginAttempt.locked_until <= now),
    )
    next_count = case(
        (expired, 1),
        else_=LoginAttempt.failed_attempts + 1,
    )
    if settings.login_max_failures == 1:
        next_lock = lock_until
    else:
        next_lock = case(
            (expired, None),
            (LoginAttempt.locked_until > now, LoginAttempt.locked_until),
            (LoginAttempt.failed_attempts + 1 >= settings.login_max_failures, lock_until),
            else_=None,
        )
    db.execute(
        update(LoginAttempt)
        .where(LoginAttempt.identifier_hash == identifier_hash)
        .values(
            failed_attempts=next_count,
            window_started_at=case(
                (expired, now),
                else_=LoginAttempt.window_started_at,
            ),
            locked_until=next_lock,
            updated_at=now,
        )
    )
    db.commit()


@router.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, db: Session = Depends(get_db), _throttle: None = Depends(register_limit)) -> TokenOut:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    now = utcnow()
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        email_verified_at=None if settings.require_email_verification else now,
        token_version=0,
    )
    verification_delivery = None
    try:
        db.add(user)
        db.flush()
        profile = Profile(user_id=user.id)
        profile.phone_number = payload.phone_number
        db.add(profile)
        db.add(UserStorageUsage(user_id=user.id, used_bytes=0))
        if settings.require_email_verification:
            token, raw_token = issue_account_token(db, user, EMAIL_VERIFICATION, now)
            verification_delivery = prepare_account_email(user, token, raw_token)
        db.commit()
    except IntegrityError:
        db.rollback()
        # Another request can register this email after the initial check.
        # Only translate a confirmed collision; preserve unrelated database errors.
        if db.query(User).filter(User.email == payload.email.lower()).first():
            raise HTTPException(
                status_code=400, detail="User with this email already exists"
            ) from None
        raise
    db.refresh(user)

    if verification_delivery is not None:
        try:
            send_account_email(*verification_delivery)
        except DeliveryError as exc:
            # The delivery adapter raises sanitized messages such as an HTTP status;
            # never log the recipient, API key, or verification URL/token.
            logger.warning("Registration verification email delivery failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Account created, but the verification email could not be sent. "
                    "Use resend verification to try again."
                ),
            ) from exc
        return verification_required_response(user)
    return token_response(user)


@router.post("/auth/login", response_model=TokenOut)
def login_user(payload: UserLogin, db: Session = Depends(get_db), _throttle: None = Depends(login_limit)) -> TokenOut:
    now = utcnow()
    email = payload.email.lower()
    identifier_hash = login_identifier_hash(email)
    locked = active_login_lock(db, identifier_hash, now)
    if locked is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after_seconds(locked, now))},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        record_login_failure(db, identifier_hash, now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    deleted = db.execute(
        delete(LoginAttempt).where(LoginAttempt.identifier_hash == identifier_hash)
    ).rowcount
    if deleted:
        db.commit()

    if settings.require_email_verification and user.email_verified_at is None:
        return verification_required_response(user)
    return token_response(user)


@router.post("/auth/verify-email", response_model=TokenOut)
def verify_email(payload: AccountTokenRequest, db: Session = Depends(get_db), _throttle: None = Depends(token_limit)) -> TokenOut:
    now = utcnow()
    account_token = claim_account_token(db, payload.token, EMAIL_VERIFICATION, now)
    if account_token is None:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user = db.get(User, account_token.user_id)
    if user is None or not user.is_active:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user.email_verified_at = now
    invalidate_other_account_tokens(db, user.id, EMAIL_VERIFICATION, account_token.id, now)
    db.commit()
    db.refresh(user)
    return token_response(user)


@router.post("/auth/resend-verification", response_model=MessageOut)
def resend_verification(
    payload: EmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _throttle: None = Depends(recovery_limit),
) -> MessageOut:
    now = utcnow()
    user = (
        db.query(User).filter(User.email == payload.email.lower(), User.is_active.is_(True)).first()
    )
    if (
        user is None
        or user.email_verified_at is not None
        or account_token_on_cooldown(db, user.id, EMAIL_VERIFICATION, now)
    ):
        return MessageOut(message=VERIFICATION_REQUEST_MESSAGE)

    token, raw_token = issue_account_token(db, user, EMAIL_VERIFICATION, now)
    delivery = prepare_account_email(user, token, raw_token)
    db.commit()
    background_tasks.add_task(deliver_account_email, delivery, "Verification email delivery failed")
    return MessageOut(message=VERIFICATION_REQUEST_MESSAGE)


@router.post("/auth/request-password-reset", response_model=MessageOut)
def request_password_reset(
    payload: EmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _throttle: None = Depends(recovery_limit),
) -> MessageOut:
    now = utcnow()
    user = (
        db.query(User).filter(User.email == payload.email.lower(), User.is_active.is_(True)).first()
    )
    if user is None or account_token_on_cooldown(db, user.id, PASSWORD_RESET, now):
        return MessageOut(message=RESET_REQUEST_MESSAGE)

    token, raw_token = issue_account_token(db, user, PASSWORD_RESET, now)
    delivery = prepare_account_email(user, token, raw_token)
    db.commit()
    background_tasks.add_task(
        deliver_account_email, delivery, "Password reset email delivery failed"
    )
    return MessageOut(message=RESET_REQUEST_MESSAGE)


@router.post("/auth/confirm-password-reset", response_model=MessageOut)
def confirm_password_reset(
    payload: PasswordResetConfirm, db: Session = Depends(get_db), _throttle: None = Depends(token_limit)
) -> MessageOut:
    now = utcnow()
    account_token = claim_account_token(db, payload.token, PASSWORD_RESET, now)
    if account_token is None:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")
    user = db.get(User, account_token.user_id)
    if user is None or not user.is_active:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token")

    user.password_hash = hash_password(payload.new_password)
    user.token_version = int(user.token_version or 0) + 1
    invalidate_other_account_tokens(db, user.id, PASSWORD_RESET, account_token.id, now)
    db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.identifier_hash == login_identifier_hash(user.email)
        )
    )
    db.commit()
    return MessageOut(message="Password reset complete. You can now log in.")


@router.get("/auth/me")
def read_current_user(current_user: User = Depends(get_current_user)) -> dict[str, str]:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
    }
