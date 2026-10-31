"""Optional email adapters. The development sink never contacts a real recipient."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

import httpx

from app.config import get_settings


class DeliveryError(Exception):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class EmailProvider(Protocol):
    def send(self, *, recipient: str, subject: str, body: str, idempotency_key: str) -> str: ...


class ResendProvider:
    def __init__(self, api_key: str, sender: str):
        self.api_key = api_key
        self.sender = sender

    def send(self, *, recipient: str, subject: str, body: str, idempotency_key: str) -> str:
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Idempotency-Key": idempotency_key,
                },
                json={"from": self.sender, "to": [recipient], "subject": subject, "text": body},
                timeout=10,
            )
        except httpx.RequestError as exc:
            raise DeliveryError("Email provider request failed; retrying safely") from exc
        if response.status_code >= 400:
            # Do not persist response bodies: provider responses can include personal data.
            raise DeliveryError(
                f"Email provider returned HTTP {response.status_code}",
                retryable=response.status_code in {408, 409, 425, 429}
                or response.status_code >= 500,
            )
        try:
            return str(response.json()["id"])
        except (KeyError, ValueError, TypeError) as exc:
            raise DeliveryError("Email provider returned an invalid response") from exc


class BrevoProvider:
    """Brevo HTTPS transactional email. Sender must be approved by Brevo.

    Brevo's send endpoint does not guarantee the same idempotency behavior as
    Resend. An ambiguous timeout may therefore result in a duplicate email.
    """

    def __init__(self, api_key: str, sender: str):
        from email.utils import parseaddr

        self.api_key = api_key
        name, address = parseaddr(sender)
        if not address or "@" not in address:
            raise ValueError("BREVO EMAIL_FROM must contain a sender email address")
        self.sender = {"name": name or "StudyVault", "email": address}

    def send(self, *, recipient: str, subject: str, body: str, idempotency_key: str) -> str:
        try:
            response = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": self.api_key, "accept": "application/json"},
                json={
                    "sender": self.sender,
                    "to": [{"email": recipient}],
                    "subject": subject,
                    "textContent": body,
                    "tags": ["studyvault"],
                },
                timeout=10,
            )
        except httpx.RequestError as exc:
            raise DeliveryError("Email provider request failed; retrying may duplicate delivery") from exc
        if response.status_code >= 400:
            raise DeliveryError(
                f"Email provider returned HTTP {response.status_code}",
                retryable=response.status_code in {408, 425, 429} or response.status_code >= 500,
            )
        try:
            return str(response.json()["messageId"])
        except (KeyError, ValueError, TypeError) as exc:
            raise DeliveryError("Email provider returned an invalid response") from exc


class FileEmailProvider:
    """Atomic per-key files are a local, inspectable and idempotent development sink."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def send(self, *, recipient: str, subject: str, body: str, idempotency_key: str) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(idempotency_key.encode()).hexdigest()
        destination = self.directory / f"{name}.json"
        payload = json.dumps(
            {"to": recipient, "subject": subject, "text": body, "idempotency_key": idempotency_key},
            ensure_ascii=False,
            indent=2,
        )
        if destination.exists():
            if destination.read_text(encoding="utf-8") != payload:
                raise DeliveryError(
                    "Email idempotency key has a different payload", retryable=False
                )
            return name
        descriptor, temporary = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            # Delivery is serialized by the database lock; replace publishes a whole file.
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return name


def configured_provider() -> EmailProvider | None:
    settings = get_settings()
    if settings.email_provider == "file":
        return FileEmailProvider(settings.email_sink_dir)
    if settings.email_provider == "resend" and settings.email_available:
        return ResendProvider(settings.resend_api_key, settings.email_from)
    if settings.email_provider == "brevo" and settings.email_available:
        return BrevoProvider(settings.brevo_api_key, settings.email_from)
    return None
