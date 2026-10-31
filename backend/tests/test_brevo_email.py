"""Brevo API integration tests with mocked HTTP responses; no external email sends."""
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.email_delivery import BrevoProvider, DeliveryError, configured_provider


def test_brevo_production_settings():
    s = Settings(
        environment="production",
        secret_key="a-strong-unique-secret-ABCD1234-zyxw9876-EXTRA",
        require_email_verification=True,
        public_frontend_url="https://studyvault-frontend.vercel.app",
        email_provider="brevo",
        brevo_api_key="test-only-key",
        email_from="StudyVault <sender@example.com>",
        _env_file=None,
    )
    assert s.email_available


def test_brevo_sends_expected_payload(monkeypatch):
    sent = []

    def fake_post(url, **kwargs):
        sent.append((url, kwargs))
        return httpx.Response(201, json={"messageId": "<test@brevo>"})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = BrevoProvider("secret-test", "StudyVault <sender@example.com>").send(
        recipient="recipient@example.com",
        subject="Verify your StudyVault email",
        body="verification message",
        idempotency_key="local-tracking-token",
    )
    assert result == "<test@brevo>"
    assert sent[0][0] == "https://api.brevo.com/v3/smtp/email"
    assert sent[0][1]["headers"]["api-key"] == "secret-test"
    payload = sent[0][1]["json"]
    assert payload["sender"] == {"name": "StudyVault", "email": "sender@example.com"}
    assert payload["to"] == [{"email": "recipient@example.com"}]
    assert payload["textContent"] == "verification message"
    assert sent[0][1]["timeout"] <= 10


@pytest.mark.parametrize("status,retryable", [(400, False), (401, False), (403, False), (429, True), (500, True)])
def test_brevo_error_mapping(monkeypatch, status, retryable):
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: httpx.Response(status))
    with pytest.raises(DeliveryError) as err:
        BrevoProvider("key", "sender@example.com").send(
            recipient="recipient@example.com", subject="test", body="hello", idempotency_key="x"
        )
    assert err.value.retryable == retryable


def test_brevo_selected_by_config(monkeypatch):
    from app import email_delivery

    monkeypatch.setattr(email_delivery, "get_settings", lambda: SimpleNamespace(
        email_provider="brevo", email_available=True,
        brevo_api_key="test-key", email_from="StudyVault <sender@example.com>",
    ))
    assert isinstance(configured_provider(), BrevoProvider)


def test_brevo_network_failure_is_generic(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("unavailable")
    monkeypatch.setattr(httpx, "post", fail)
    with pytest.raises(DeliveryError, match="request failed"):
        BrevoProvider("key", "sender@example.com").send(
            recipient="recipient@example.com", subject="test", body="hello", idempotency_key="x"
        )
