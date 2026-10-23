"""Atomic database-backed per-client IP limits on public auth endpoints.

All API workers must share the same database. IPs are keyed with HMAC, not
stored in plaintext. Deploy behind the project's Caddy ingress so Uvicorn
receives a trusted, overwritten X-Forwarded-For value. Never expose the API
container's port directly to the internet.
"""
from __future__ import annotations

import hashlib
import hmac
import math
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.datetime_type import utcnow
from app.models import PublicRateLimit


def client_limit_key(ip: str, bucket: str, secret: str) -> str:
    return hmac.new(secret.encode(), f"{bucket}:{ip}".encode(), hashlib.sha256).hexdigest()


def enforce_limit(db: Session, ip: str, bucket: str, maximum: int, window_seconds: int) -> None:
    """Increment an atomically upserted window counter and reject beyond the quota."""
    settings = get_settings()
    if not settings.public_auth_limit_enabled:
        return
    now = utcnow()
    key_hash = client_limit_key(ip, bucket, settings.secret_key)
    cutoff = now - timedelta(seconds=window_seconds)
    table = PublicRateLimit.__table__
    values = {"key_hash": key_hash, "hits": 1, "window_started_at": now, "updated_at": now}
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgres_insert(table).values(**values)
    elif dialect == "sqlite":
        statement = sqlite_insert(table).values(**values)
    else:
        raise RuntimeError("Public API rate limiting requires PostgreSQL or SQLite")
    expired = table.c.window_started_at <= cutoff
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.key_hash],
        set_={
            "hits": case((expired, 1), else_=table.c.hits + 1),
            "window_started_at": case((expired, now), else_=table.c.window_started_at),
            "updated_at": now,
        },
    ).returning(table.c.hits, table.c.window_started_at)
    hits, started = db.execute(statement).one()
    # Must commit independently of registration/login; failed requests also consume quota.
    db.commit()
    if hits > maximum:
        remaining = max(1, math.ceil((started + timedelta(seconds=window_seconds) - now).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(remaining)},
        )


def _limit(request: Request, db: Session, bucket: str, maximum: int) -> None:
    # The reverse proxy must overwrite X-Forwarded-For. Request.client is the
    # address accepted by Uvicorn's trusted-proxy handling, not arbitrary headers.
    ip = request.client.host if request.client else "unknown"
    enforce_limit(db, ip, bucket, maximum, 60 * 60)


def register_limit(request: Request, db: Session = Depends(get_db)) -> None:
    _limit(request, db, "register", get_settings().register_per_hour)


def login_limit(request: Request, db: Session = Depends(get_db)) -> None:
    _limit(request, db, "login", get_settings().login_per_hour)


def recovery_limit(request: Request, db: Session = Depends(get_db)) -> None:
    _limit(request, db, "recovery", get_settings().recovery_per_hour)


def token_limit(request: Request, db: Session = Depends(get_db)) -> None:
    _limit(request, db, "token", get_settings().recovery_per_hour)
