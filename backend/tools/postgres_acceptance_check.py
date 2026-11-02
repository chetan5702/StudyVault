"""End-to-end API acceptance checks on disposable PostgreSQL CI only.

The database guard deliberately refuses to run against staging/production.
External email and S3 are tested separately, not accessed by this script.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal, engine
from app.main import app
from app.reminders import run_due_reminders


def check(response, expected: int, label: str):
    assert response.status_code == expected, (
        f"{label}: HTTP {response.status_code}, expected {expected}; "
        f"body={response.text[:500]}"
    )
    print(f"PASS {label}: HTTP {expected}", flush=True)
    return response


def register(client: TestClient, email: str):
    result = check(
        client.post(
            "/api/v1/auth/register",
            json={"full_name": "CI Student", "email": email, "password": "CIOnlyPassword123!"},
        ),
        201,
        f"register {email}",
    ).json()
    assert result["access_token"]
    return {"Authorization": f"Bearer {result['access_token']}"}


def pdf_contents() -> bytes:
    output = BytesIO()
    document = PdfWriter()
    document.add_blank_page(width=150, height=150)
    document.write(output)
    return output.getvalue()


def upload(client, headers, subject_id, data, **kwargs):
    return client.post(
        "/api/v1/materials/upload",
        headers=headers,
        params={"subject_id": subject_id, "title": "PostgreSQL CI PDF", **kwargs},
        files={"file": ("acceptance.pdf", data, "application/pdf")},
    )


def main():
    settings = get_settings()
    # Fail closed: never execute this test against live or persistent data.
    if not (
        settings.environment == "test"
        and settings.database_url.startswith("postgresql")
        and settings.database_url.split("?")[0].endswith("/studyvault_ci")
        and settings.storage_backend == "local"
        and not settings.require_email_verification
    ):
        raise SystemExit("Refusing PostgreSQL API acceptance checks outside isolated CI")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0007_public_limits_and_membership"
        )
    print("PASS PostgreSQL schema revision", flush=True)
    doc = pdf_contents()

    with TestClient(app) as client:
        owner = register(client, "pg-owner@example.com")
        outsider = register(client, "pg-outsider@example.com")
        check(client.get("/api/v1/materials"), 401, "unauthenticated library blocked")
        created = check(
            client.post(
                "/api/v1/subjects",
                headers=owner,
                json={"code": "PG-TEST", "name": "Postgres integration"},
            ),
            201,
            "create subject",
        ).json()
        sid = created["id"]
        check(client.get(f"/api/v1/subjects/{sid}", headers=outsider), 404, "subject isolation")

        own_upload = check(upload(client, owner, sid, doc), 201, "upload PDF").json()
        fid = own_upload["id"]
        assert own_upload["size_bytes"] == len(doc)
        assert check(
            client.get(f"/api/v1/materials/{fid}/download", headers=owner),
            200,
            "download PDF",
        ).content == doc
        check(client.get(f"/api/v1/materials/{fid}/download", headers=outsider), 404, "private download isolation")
        check(client.get(f"/api/v1/materials/{fid}", headers=outsider), 404, "private metadata isolation")
        check(client.delete(f"/api/v1/materials/{fid}", headers=outsider), 404, "private delete isolation")
        check(upload(client, outsider, sid, doc), 404, "cross-account upload blocked")
        assert client.get("/api/v1/materials", headers=outsider).json() == []

        before_delete = check(client.get("/api/v1/materials/config", headers=owner), 200, "quota endpoint").json()
        assert before_delete["used_storage_bytes"] == len(doc)
        check(client.delete(f"/api/v1/materials/{fid}", headers=owner), 200, "owner deletes PDF")
        check(client.get(f"/api/v1/materials/{fid}/download", headers=owner), 404, "deleted PDF unavailable")
        assert client.get("/api/v1/materials/config", headers=owner).json()["used_storage_bytes"] == 0
        print("PASS quota recovered after deletion", flush=True)

        group = check(
            client.post("/api/v1/groups", headers=owner, json={"name": "PG CI group"}),
            201,
            "create study group",
        ).json()
        shared = check(
            upload(client, owner, sid, doc, visibility="group", group_id=group["id"]),
            201,
            "upload group PDF",
        ).json()
        shared_id = shared["id"]
        check(client.get(f"/api/v1/materials/{shared_id}/download", headers=outsider), 404, "group file denied before join")
        check(
            client.post("/api/v1/groups/join", headers=outsider, params={"invite_code": group["invite_code"]}),
            200,
            "join study group",
        )
        assert check(
            client.get(f"/api/v1/materials/{shared_id}/download", headers=outsider),
            200,
            "member downloads group PDF",
        ).content == doc
        check(client.delete(f"/api/v1/materials/{shared_id}", headers=outsider), 404, "member cannot delete owner's PDF")
        check(client.delete(f"/api/v1/materials/{shared_id}", headers=owner), 200, "owner deletes group PDF")

        prefs = check(
            client.put(
                "/api/v1/notification-preferences",
                headers=owner,
                json={
                    "in_app_enabled": True, "email_enabled": False,
                    "reminder_minutes": [60], "timezone": "UTC",
                },
            ),
            200,
            "configure in-app reminders",
        ).json()
        assert prefs["in_app_enabled"] is True

        exam_at = datetime.now(UTC) + timedelta(hours=2)
        exam = check(
            client.post(
                "/api/v1/exams",
                headers=owner,
                json={"subject_id": sid, "title": "PostgreSQL exam reminder", "scheduled_for": exam_at.isoformat()},
            ),
            201,
            "create future exam",
        ).json()
        first = run_due_reminders(SessionLocal, now=exam_at - timedelta(hours=1))
        assert first["delivered"] == 1, first
        second = run_due_reminders(SessionLocal, now=exam_at - timedelta(hours=1))
        assert second["delivered"] == 0, second
        notice = check(client.get("/api/v1/notifications", headers=owner), 200, "read notifications").json()
        assert notice["unread_count"] == 1 and len(notice["items"]) == 1, notice
        assert notice["items"][0]["exam_id"] == exam["id"]
        assert client.get("/api/v1/notifications", headers=outsider).json()["items"] == []
        check(
            client.patch(f"/api/v1/notifications/{notice['items'][0]['id']}/read", headers=owner),
            200,
            "mark notification read",
        )
        assert client.get("/api/v1/notifications", headers=owner).json()["unread_count"] == 0
        print("PASS scheduled reminder delivered once, private, and mark-read works", flush=True)

    print("PASS ALL disposable PostgreSQL API acceptance checks", flush=True)


if __name__ == "__main__":
    main()
