from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.v1 import auth
from app.database import SessionLocal
from app.main import app
from app.models import Profile, User


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_register_login_flow() -> None:
    with TestClient(app) as client:
        payload = {
            "full_name": "Test Student",
            "email": "student@example.com",
            "password": "Password123!",
        }
        register = client.post("/api/v1/auth/register", json=payload)
        assert register.status_code == 201, register.text

        login = client.post(
            "/api/v1/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
        assert login.status_code == 200, login.text
        assert "access_token" in login.json()


@pytest.mark.parametrize(
    ("submitted", "stored"),
    [
        ("+91 (98765) 43210", "+919876543210"),
        ("020 7946-0958", "02079460958"),
    ],
)
def test_registration_normalizes_and_persists_optional_phone_number(
    client, submitted, stored
) -> None:
    register = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Phone Student",
            "email": "phone@example.com",
            "password": "Password123!",
            "phone_number": submitted,
        },
    )
    assert register.status_code == 201, register.text
    assert "phone_number" not in register.json()["user"]

    profile = client.get(
        "/api/v1/profile/me",
        headers={"Authorization": "Bearer " + register.json()["access_token"]},
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["phone_number"] == stored

    with SessionLocal() as db:
        assert db.query(Profile).one().phone_number == stored


@pytest.mark.parametrize("submitted", [None, "", "   "])
def test_registration_allows_an_omitted_or_blank_phone_number(client, submitted) -> None:
    payload = {
        "full_name": "No Phone Student",
        "email": "no-phone@example.com",
        "password": "Password123!",
    }
    if submitted is not None:
        payload["phone_number"] = submitted

    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    with SessionLocal() as db:
        assert db.query(Profile).one().phone_number is None


@pytest.mark.parametrize(
    "submitted",
    [
        "+12 34 56",
        "+1234567890123456",
        "+01234567",
        "+1+2025550100",
        "202.555.0100",
        "phone 2025550100",
        "2025550100 ext 4",
        "+1 (202) 555-0100          ",
    ],
)
def test_registration_rejects_invalid_phone_numbers(client, submitted) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Invalid Phone Student",
            "email": "invalid-phone@example.com",
            "password": "Password123!",
            "phone_number": submitted,
        },
    )
    assert response.status_code == 422, response.text

    with SessionLocal() as db:
        assert db.query(User).count() == 0
        assert db.query(Profile).count() == 0


def test_profile_update_uses_the_same_phone_number_normalization(client, student) -> None:
    updated = client.put(
        "/api/v1/profile/me",
        headers=student,
        json={"phone_number": "+1 (202) 555-0100"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["phone_number"] == "+12025550100"

    cleared = client.put("/api/v1/profile/me", headers=student, json={"phone_number": "  "})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["phone_number"] is None


def test_registration_email_race_returns_duplicate_without_changing_winner(
    client, monkeypatch
) -> None:
    payload = {
        "full_name": "Losing Student",
        "email": "Racing.Student@example.com",
        "password": "Password123!",
    }
    winner_password = "WinnerPassword123!"
    winner_hash = auth.hash_password(winner_password)
    original_hash = auth.hash_password

    def register_winner_after_precheck(password):
        # Commit on an independent connection after the endpoint's SELECT and
        # before its INSERT, deterministically reproducing two racing requests.
        with SessionLocal() as competing_db:
            winner = User(
                email=payload["email"].lower(),
                password_hash=winner_hash,
                full_name="Winning Student",
            )
            competing_db.add(winner)
            competing_db.flush()
            competing_db.add(Profile(user_id=winner.id))
            competing_db.commit()
        return original_hash(password)

    monkeypatch.setattr(auth, "hash_password", register_winner_after_precheck)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400, response.text
    assert response.json() == {"detail": "User with this email already exists"}

    with SessionLocal() as db:
        winner = db.query(User).one()
        assert winner.email == payload["email"].lower()
        assert winner.full_name == "Winning Student"
        assert winner.password_hash == winner_hash
        assert db.query(Profile).one().user_id == winner.id

    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": winner_password},
    )
    assert login.status_code == 200, login.text
    losing_login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert losing_login.status_code == 401


@pytest.mark.parametrize("failure_stage", ["user_flush", "profile_commit"])
def test_registration_rolls_back_and_preserves_unrelated_integrity_errors(
    client, monkeypatch, failure_stage
) -> None:
    if failure_stage == "user_flush":
        monkeypatch.setattr(auth, "hash_password", lambda password: None)
    else:
        monkeypatch.setattr(auth, "Profile", lambda user_id: Profile(user_id=None))

    with pytest.raises(IntegrityError, match="NOT NULL constraint failed"):
        client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Student",
                "email": "failed@example.com",
                "password": "Password123!",
            },
        )

    with SessionLocal() as db:
        assert db.query(User).count() == 0
        assert db.query(Profile).count() == 0
