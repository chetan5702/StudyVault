from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, BrokenBarrierError

from fastapi.testclient import TestClient

from app.api.v1 import auth
from app.database import SessionLocal, engine
from app.main import app
from app.models import LoginAttempt, UserStorageUsage
from app.storage import ensure_storage
from tests.test_workflow import P, second, subject, upload


def test_login_failures_persist_and_lock_with_retry_after(client, student, monkeypatch):
    now = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(auth, "utcnow", lambda: now)
    monkeypatch.setattr(auth.settings, "login_max_failures", 2)
    monkeypatch.setattr(auth.settings, "login_failure_window_seconds", 120)
    monkeypatch.setattr(auth.settings, "login_lockout_seconds", 60)
    credentials = {"email": "ONE@EXAMPLE.COM", "password": "wrong-password"}

    assert client.post(P + "/auth/login", json=credentials).status_code == 401
    assert client.post(P + "/auth/login", json=credentials).status_code == 401

    identifier_hash = auth.login_identifier_hash(credentials["email"])
    with SessionLocal() as db:
        attempt = db.get(LoginAttempt, identifier_hash)
        assert attempt is not None
        assert attempt.failed_attempts == 2
        assert attempt.identifier_hash != credentials["email"].lower()
        assert attempt.locked_until == now + timedelta(seconds=60)

    # A fresh connection pool observes the same database-backed lockout state.
    engine.dispose()
    blocked = client.post(
        P + "/auth/login",
        json={"email": credentials["email"], "password": "Password123!"},
    )
    assert blocked.status_code == 429, blocked.text
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.json()["detail"] == "Too many login attempts. Try again later."

    now += timedelta(seconds=61)
    logged_in = client.post(
        P + "/auth/login",
        json={"email": credentials["email"], "password": "Password123!"},
    )
    assert logged_in.status_code == 200, logged_in.text
    with SessionLocal() as db:
        assert db.get(LoginAttempt, identifier_hash) is None


def test_successful_login_resets_failure_counter(client, student, monkeypatch):
    fixed_now = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(auth, "utcnow", lambda: fixed_now)
    monkeypatch.setattr(auth.settings, "login_max_failures", 2)
    credentials = {"email": "one@example.com", "password": "Password123!"}

    assert (
        client.post(P + "/auth/login", json={**credentials, "password": "wrong"}).status_code == 401
    )
    assert client.post(P + "/auth/login", json=credentials).status_code == 200
    assert (
        client.post(P + "/auth/login", json={**credentials, "password": "wrong"}).status_code == 401
    )

    with SessionLocal() as db:
        attempt = db.get(LoginAttempt, auth.login_identifier_hash(credentials["email"]))
        assert attempt is not None
        assert attempt.failed_attempts == 1
        assert attempt.locked_until is None


def test_cumulative_storage_quota_rejects_and_cleans_upload_then_releases_on_delete(
    client, student, pdf, monkeypatch
):
    from app.api.v1 import materials

    monkeypatch.setattr(materials.get_settings(), "max_user_storage_bytes", len(pdf))
    subject_id = subject(client, student)

    before = client.get(P + "/materials/config", headers=student)
    assert before.status_code == 200
    assert before.json()["max_user_storage_bytes"] == len(pdf)
    assert before.json()["used_storage_bytes"] == 0

    first = upload(client, student, subject_id, pdf)
    assert first.status_code == 201, first.text
    rejected = upload(client, student, subject_id, pdf)
    assert rejected.status_code == 413, rejected.text
    assert rejected.json()["detail"] == "Storage quota exceeded"
    assert len(client.get(P + "/materials", headers=student).json()) == 1
    assert len(list(ensure_storage().iterdir())) == 1

    user_id = client.get(P + "/auth/me", headers=student).json()["id"]
    with SessionLocal() as db:
        usage = db.get(UserStorageUsage, user_id)
        assert usage is not None
        assert usage.used_bytes == len(pdf)

    current = client.get(P + "/materials/config", headers=student).json()
    assert current["used_storage_bytes"] == len(pdf)
    assert current["remaining_storage_bytes"] == 0

    deleted = client.delete(P + f"/materials/{first.json()['id']}", headers=student)
    assert deleted.status_code == 200, deleted.text
    assert list(ensure_storage().iterdir()) == []
    with SessionLocal() as db:
        assert db.get(UserStorageUsage, user_id).used_bytes == 0

    replacement = upload(client, student, subject_id, pdf)
    assert replacement.status_code == 201, replacement.text


def test_storage_quota_is_isolated_per_owner(client, student, pdf, monkeypatch):
    from app.api.v1 import materials

    monkeypatch.setattr(materials.get_settings(), "max_user_storage_bytes", len(pdf))
    first_subject = subject(client, student)
    other = second(client)
    other_subject = subject(client, other, "CS202")

    assert upload(client, student, first_subject, pdf).status_code == 201
    assert upload(client, other, other_subject, pdf).status_code == 201
    assert upload(client, student, first_subject, pdf).status_code == 413
    assert len(client.get(P + "/materials", headers=student).json()) == 1
    assert len(client.get(P + "/materials", headers=other).json()) == 1


def test_concurrent_material_deletes_release_storage_once(client, student, pdf, monkeypatch):
    from app.api.v1 import materials

    subject_id = subject(client, student)
    deleted_material = upload(client, student, subject_id, pdf)
    retained_material = upload(client, student, subject_id, pdf)
    assert deleted_material.status_code == 201, deleted_material.text
    assert retained_material.status_code == 201, retained_material.text

    user_id = client.get(P + "/auth/me", headers=student).json()["id"]
    material_id = deleted_material.json()["id"]

    # Hold the first deletion at quota release long enough for the second
    # request to contend for the same row. Before the atomic delete fix, both
    # requests had already loaded the material and could both release quota.
    release_barrier = Barrier(2)
    original_release_storage = materials.release_storage

    def synchronized_release(db, owner_id, size_bytes):
        try:
            release_barrier.wait(timeout=0.5)
        except BrokenBarrierError:
            pass
        original_release_storage(db, owner_id, size_bytes)

    monkeypatch.setattr(materials, "release_storage", synchronized_release)
    request_barrier = Barrier(2)

    def issue_delete(request_client):
        request_barrier.wait(timeout=2)
        return request_client.delete(P + f"/materials/{material_id}", headers=student)

    # Each HTTP request receives its own SQLAlchemy session through get_db.
    with TestClient(app) as first_client, TestClient(app) as second_client:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(issue_delete, first_client),
                executor.submit(issue_delete, second_client),
            ]
            responses = [future.result(timeout=5) for future in futures]

    assert sorted(response.status_code for response in responses) == [200, 404]
    assert len(client.get(P + "/materials", headers=student).json()) == 1
    assert (
        client.get(P + f"/materials/{retained_material.json()['id']}", headers=student).status_code
        == 200
    )
    assert len(list(ensure_storage().iterdir())) == 1
    with SessionLocal() as db:
        usage = db.get(UserStorageUsage, user_id)
        assert usage is not None
        assert usage.used_bytes == len(pdf)
