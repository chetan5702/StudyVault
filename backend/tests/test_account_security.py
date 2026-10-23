from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from app import account_security
from app.api.v1 import auth
from app.config import Settings
from app.database import SessionLocal
from app.email_delivery import DeliveryError
from app.models import AccountToken, User

P = "/api/v1"


class CapturingProvider:
    def __init__(self):
        self.calls = []

    def send(self, *, recipient, subject, body, idempotency_key):
        self.calls.append(
            {
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "idempotency_key": idempotency_key,
            }
        )
        return "delivery-id"


class FailingProvider:
    def send(self, **_kwargs):
        raise DeliveryError("provider unavailable")


def token_from_delivery(call):
    url = next(part for part in call["body"].split() if part.startswith("http"))
    return parse_qs(urlparse(url).query)["token"][0]


def enable_verification(monkeypatch, clock):
    provider = CapturingProvider()
    monkeypatch.setattr(auth.settings, "require_email_verification", True)
    monkeypatch.setattr(auth, "utcnow", lambda: clock["now"])
    monkeypatch.setattr(account_security, "configured_provider", lambda: provider)
    return provider


def test_registration_verification_uses_hashed_single_use_token(client, monkeypatch):
    clock = {"now": datetime(2030, 1, 1, 12, 0, tzinfo=UTC)}
    provider = enable_verification(monkeypatch, clock)
    payload = {
        "full_name": "Verify Student",
        "email": "verify@example.com",
        "password": "Password123!",
    }

    registered = client.post(P + "/auth/register", json=payload)
    assert registered.status_code == 201, registered.text
    assert registered.json()["access_token"] is None
    assert registered.json()["verification_required"] is True
    assert len(provider.calls) == 1
    assert provider.calls[0]["idempotency_key"].startswith("studyvault-account-email_verification-")
    raw_token = token_from_delivery(provider.calls[0])

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == payload["email"]).one()
        stored = db.query(AccountToken).one()
        assert user.email_verified_at is None
        assert stored.token_digest == account_security.account_token_digest(raw_token)
        assert raw_token != stored.token_digest
        assert raw_token not in "|".join(
            str(value)
            for value in (
                stored.id,
                stored.user_id,
                stored.purpose,
                stored.token_digest,
                stored.expires_at,
                stored.used_at,
                stored.created_at,
            )
        )

    login = client.post(
        P + "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200
    assert login.json()["access_token"] is None
    assert login.json()["verification_required"] is True

    verified = client.post(P + "/auth/verify-email", json={"token": raw_token})
    assert verified.status_code == 200, verified.text
    assert verified.json()["access_token"]
    assert verified.json()["verification_required"] is False
    headers = {"Authorization": "Bearer " + verified.json()["access_token"]}
    assert client.get(P + "/auth/me", headers=headers).status_code == 200

    reused = client.post(P + "/auth/verify-email", json={"token": raw_token})
    assert reused.status_code == 400
    with SessionLocal() as db:
        assert db.query(User).one().email_verified_at == clock["now"]
        assert db.query(AccountToken).one().used_at == clock["now"]


def test_verification_resend_is_generic_cooled_down_and_invalidates_old_token(client, monkeypatch):
    clock = {"now": datetime(2030, 1, 1, 12, 0, tzinfo=UTC)}
    provider = enable_verification(monkeypatch, clock)
    monkeypatch.setattr(auth.settings, "verification_resend_cooldown_seconds", 60)
    payload = {
        "full_name": "Verify Student",
        "email": "verify@example.com",
        "password": "Password123!",
    }
    assert client.post(P + "/auth/register", json=payload).status_code == 201
    original_token = token_from_delivery(provider.calls[0])

    immediate = client.post(P + "/auth/resend-verification", json={"email": payload["email"]})
    unknown = client.post(P + "/auth/resend-verification", json={"email": "unknown@example.com"})
    assert immediate.status_code == unknown.status_code == 200
    assert immediate.json() == unknown.json()
    assert len(provider.calls) == 1

    clock["now"] += timedelta(seconds=61)
    resent = client.post(P + "/auth/resend-verification", json={"email": payload["email"]})
    assert resent.status_code == 200
    assert len(provider.calls) == 2
    replacement_token = token_from_delivery(provider.calls[1])
    assert replacement_token != original_token
    assert client.post(P + "/auth/verify-email", json={"token": original_token}).status_code == 400
    assert (
        client.post(P + "/auth/verify-email", json={"token": replacement_token}).status_code == 200
    )


def test_password_reset_is_enumeration_safe_single_use_and_revokes_access(
    client, student, monkeypatch
):
    clock = {"now": datetime(2030, 1, 1, 12, 0, tzinfo=UTC)}
    provider = CapturingProvider()
    monkeypatch.setattr(auth, "utcnow", lambda: clock["now"])
    monkeypatch.setattr(account_security, "configured_provider", lambda: provider)

    existing = client.post(P + "/auth/request-password-reset", json={"email": "one@example.com"})
    unknown = client.post(P + "/auth/request-password-reset", json={"email": "unknown@example.com"})
    assert existing.status_code == unknown.status_code == 200
    assert existing.json() == unknown.json()
    assert len(provider.calls) == 1
    assert provider.calls[0]["idempotency_key"].startswith("studyvault-account-password_reset-")
    raw_token = token_from_delivery(provider.calls[0])

    reset = client.post(
        P + "/auth/confirm-password-reset",
        json={"token": raw_token, "new_password": "NewPassword123!"},
    )
    assert reset.status_code == 200, reset.text
    assert client.get(P + "/auth/me", headers=student).status_code == 401
    assert (
        client.post(
            P + "/auth/confirm-password-reset",
            json={"token": raw_token, "new_password": "AnotherPassword123!"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            P + "/auth/login",
            json={"email": "one@example.com", "password": "Password123!"},
        ).status_code
        == 401
    )
    new_login = client.post(
        P + "/auth/login",
        json={"email": "one@example.com", "password": "NewPassword123!"},
    )
    assert new_login.status_code == 200, new_login.text

    with SessionLocal() as db:
        user = db.query(User).one()
        token = db.query(AccountToken).one()
        assert user.token_version == 1
        assert token.used_at == clock["now"]
        assert token.token_digest == account_security.account_token_digest(raw_token)


def test_expired_account_token_is_rejected(client, student, monkeypatch):
    clock = {"now": datetime(2030, 1, 1, 12, 0, tzinfo=UTC)}
    provider = CapturingProvider()
    monkeypatch.setattr(auth, "utcnow", lambda: clock["now"])
    monkeypatch.setattr(account_security, "configured_provider", lambda: provider)
    monkeypatch.setattr(auth.settings, "password_reset_token_expire_minutes", 1)

    assert (
        client.post(
            P + "/auth/request-password-reset", json={"email": "one@example.com"}
        ).status_code
        == 200
    )
    raw_token = token_from_delivery(provider.calls[0])
    clock["now"] += timedelta(minutes=2)
    expired = client.post(
        P + "/auth/confirm-password-reset",
        json={"token": raw_token, "new_password": "NewPassword123!"},
    )
    assert expired.status_code == 400
    assert client.get(P + "/auth/me", headers=student).status_code == 200


def test_password_reset_request_stays_generic_when_background_delivery_fails(
    client, student, monkeypatch
):
    monkeypatch.setattr(account_security, "configured_provider", lambda: FailingProvider())

    response = client.post(P + "/auth/request-password-reset", json={"email": "one@example.com"})

    assert response.status_code == 200
    assert response.json() == {"message": auth.RESET_REQUEST_MESSAGE}


def test_production_requires_verified_email_provider_and_https_frontend():
    secure = {
        "environment": "production",
        "secret_key": "secure-production-secret-4f7a93c8b2e165d0",
        "require_email_verification": True,
        "email_provider": "resend",
        "resend_api_key": "re_test_key",
        "email_from": "StudyVault <security@example.com>",
        "public_frontend_url": "https://studyvault.example.com",
        "_env_file": None,
    }
    assert Settings(**secure).require_email_verification is True

    for changes in (
        {"require_email_verification": False},
        {"email_provider": "disabled"},
        {"email_provider": "file"},
        {"resend_api_key": ""},
        {"public_frontend_url": "http://studyvault.example.com"},
        {"public_frontend_url": "https://localhost"},
    ):
        with pytest.raises(ValueError):
            Settings(**{**secure, **changes})
