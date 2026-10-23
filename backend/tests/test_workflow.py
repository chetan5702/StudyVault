from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings

P = "/api/v1"


def subject(client, headers, code="CS101"):
    r = client.post(
        P + "/subjects",
        headers=headers,
        json={"code": code, "name": "Computer Science"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(client, headers, sid, pdf, **params):
    return client.post(
        P + "/materials/upload",
        headers=headers,
        params={"subject_id": sid, "title": "Lecture notes", **params},
        files={"file": ("../../notes.pdf", pdf, "application/pdf")},
    )


def second(client):
    r = client.post(
        P + "/auth/register",
        json={
            "full_name": "Second Student",
            "email": "two@example.com",
            "password": "Password123!",
        },
    )
    assert r.status_code == 201
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_complete_workflow(client, student, pdf):
    assert client.get(P + "/dashboard", headers=student).json()["next_exam"] is None
    assert (
        client.put(
            P + "/profile/me",
            headers=student,
            json={"academic_year": "2026-27", "semester": 1, "section": "A"},
        ).status_code
        == 200
    )
    sid = subject(client, student)
    unit = client.post(
        P + f"/subjects/{sid}/units",
        headers=student,
        json={"subject_id": sid, "name": "Introduction"},
    ).json()
    r = upload(client, student, sid, pdf, unit_id=unit["id"])
    assert r.status_code == 201, r.text
    material = r.json()
    assert material["size_bytes"] == len(pdf)
    assert material["file_name"] == "notes.pdf"
    assert "storage_key" not in material
    assert client.get(P + "/materials", headers=student).json()[0]["id"] == material["id"]
    assert client.get(P + f"/materials/{material['id']}/download", headers=student).content == pdf
    date = datetime.now(UTC) + timedelta(days=3)
    r = client.post(
        P + "/exams",
        headers=student,
        json={"subject_id": sid, "title": "Midterm", "scheduled_for": date.isoformat()},
    )
    assert r.status_code == 201, r.text
    dashboard = client.get(P + "/dashboard", headers=student).json()
    assert dashboard["stats"]["subjects"] == 1
    assert dashboard["stats"]["materials"] == 1
    assert datetime.fromisoformat(dashboard["next_exam"]["scheduled_for"]) == date
    login = client.post(
        P + "/auth/login", json={"email": "one@example.com", "password": "Password123!"}
    ).json()
    again = {"Authorization": "Bearer " + login["access_token"]}
    assert len(client.get(P + "/subjects", headers=again).json()) == 1
    assert len(client.get(P + "/exams", headers=again).json()) == 1
    other = second(client)
    assert client.get(P + "/materials", headers=other).json() == []
    for suffix in ["", "/download"]:
        assert (
            client.get(P + f"/materials/{material['id']}" + suffix, headers=other).status_code
            == 404
        )
    assert client.get(P + f"/subjects/{sid}", headers=other).status_code == 404
    assert upload(client, other, sid, pdf).status_code == 404


@pytest.mark.parametrize("contents", [b"", b"not a pdf", b"%PDF-1.7\nforged"])
def test_reject_invalid_files(client, student, contents):
    sid = subject(client, student)
    assert upload(client, student, sid, contents).status_code == 400
    assert client.get(P + "/materials", headers=student).json() == []
    from app.storage import ensure_storage

    assert list(ensure_storage().iterdir()) == []


def test_stream_limit(client, student, pdf, monkeypatch):
    from app.storage import ensure_storage, settings

    monkeypatch.setattr(settings, "max_upload_size_bytes", len(pdf) - 1)
    assert upload(client, student, subject(client, student), pdf).status_code == 413
    assert list(ensure_storage().iterdir()) == []


def test_wrong_unit(client, student, pdf):
    a, b = subject(client, student), subject(client, student, "CS102")
    unit = client.post(
        P + f"/subjects/{b}/units",
        headers=student,
        json={"subject_id": b, "name": "Wrong unit"},
    ).json()
    assert upload(client, student, a, pdf, unit_id=unit["id"]).status_code == 400


def test_group_permissions(client, student, pdf):
    sid = subject(client, student)
    group = client.post(P + "/groups", headers=student, json={"name": "Study group"}).json()
    other = second(client)
    other_sid = subject(client, other)
    assert (
        upload(client, other, other_sid, pdf, visibility="group", group_id=group["id"]).status_code
        == 403
    )
    assert upload(client, student, sid, pdf, visibility="group").status_code == 400
    material = upload(client, student, sid, pdf, visibility="group", group_id=group["id"]).json()
    url = P + f"/materials/{material['id']}/download"
    assert client.get(url, headers=other).status_code == 404
    assert (
        client.post(
            P + "/groups/join",
            headers=other,
            params={"invite_code": group["invite_code"]},
        ).status_code
        == 200
    )
    assert client.get(url, headers=other).content == pdf
    assert len(client.get(P + "/materials", headers=other).json()) == 1
    assert client.delete(P + f"/materials/{material['id']}", headers=other).status_code == 404


def test_commit_failure_cleanup(client, student, pdf, monkeypatch):
    from sqlalchemy.orm import Session

    from app.storage import ensure_storage

    sid = subject(client, student)

    def fail(self):
        raise RuntimeError("Simulated database failure")

    monkeypatch.setattr(Session, "commit", fail)
    with pytest.raises(RuntimeError):
        upload(client, student, sid, pdf)
    assert list(ensure_storage().iterdir()) == []
    assert client.get(P + "/materials", headers=student).json() == []


def test_auth_failures(client, student):
    assert client.get(P + "/subjects").status_code == 401
    assert (
        client.get(P + "/subjects", headers={"Authorization": "Bearer broken"}).status_code == 401
    )
    assert (
        client.post(
            P + "/auth/login", json={"email": "one@example.com", "password": "wrong"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            P + "/auth/register",
            json={
                "full_name": "A",
                "email": "one@example.com",
                "password": "Password123!",
            },
        ).status_code
        == 400
    )


def test_production_configuration():
    for key in ["", "dev-secret-key-change-me", "x" * 48]:
        with pytest.raises(ValueError):
            Settings(environment="production", secret_key=key, _env_file=None)
    with pytest.raises(ValueError):
        Settings(
            environment="production",
            secret_key="abcdefghijklmnopqrstuvwxyz0123456789",
            seed_demo=True,
            _env_file=None,
        )
