from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import TokenData, get_settings

settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if len(plain_password.encode("utf-8")) > 72:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(
    subject: str,
    email: str,
    full_name: str,
    expires_delta: timedelta | None = None,
    token_version: int = 0,
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "full_name": full_name,
        "ver": token_version,
        "exp": expire,
    }
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> TokenData:
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        options={"require_exp": True, "require_sub": True},
    )
    return TokenData(
        user_id=str(payload["sub"]),
        email=str(payload["email"]),
        full_name=str(payload["full_name"]),
        token_version=int(payload.get("ver", 0)),
    )


def validate_token(token: str) -> TokenData:
    try:
        return decode_access_token(token)
    except (JWTError, KeyError, TypeError) as exc:
        raise ValueError("Invalid or expired token") from exc
