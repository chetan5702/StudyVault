"""University-domain registration policy, legacy account compatibility and verification."""
import pytest

from app.config import get_settings, Settings
from app.database import SessionLocal
from app.models import User, Profile

P = "/api/v1/auth"

@pytest.mark.parametrize("email", [
    "student@suh.edu.in",
    "25011cseai0046@aiml.suh.edu.in",
    "2501100@cse.suh.edu.in",
    "2501100@ds.suh.edu.in",
    "STUDENT@AIML.SUH.EDU.IN",
    "student@dept.cs.suh.edu.in",
])
def test_university_domain_registration_allowed(client, monkeypatch, email):
    monkeypatch.setattr(get_settings(), "registration_email_domain", "suh.edu.in")
    response = client.post(P + "/register", json={
        "full_name": "Student", "email": email, "password": "Password123!"
    })
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("email", [
    "student@gmail.com", "student@yahoo.com",
    "student@fakesuh.edu.in", "student@suh.edu.in.fake.com",
    "student@othersuh.edu.in", "student@malicious-suh.edu.in",
])
def test_nonuniversity_registration_rejected_without_database_write(client, monkeypatch, email):
    monkeypatch.setattr(get_settings(), "registration_email_domain", "suh.edu.in")
    response = client.post(P + "/register", json={
        "full_name": "Student", "email": email, "password": "Password123!"
    })
    assert response.status_code == 422, response.text
    assert "university email" in response.text
    with SessionLocal() as db:
        assert db.query(User).count() == 0


def test_legacy_account_login_and_recovery_remain_eligible(client, monkeypatch):
    # Register a legacy Gmail user as before the new policy.
    from app.security import hash_password
    with SessionLocal() as db:
        user = User(email="legacy@example.com", full_name="Existing account", password_hash=hash_password("Password123!"))
        db.add(user)
        db.flush()
        db.add(Profile(user_id=user.id))
        db.commit()

    monkeypatch.setattr(get_settings(), "registration_email_domain", "suh.edu.in")
    login = client.post(P + "/login", json={"email": "legacy@example.com", "password": "Password123!"})
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]
    recovery = client.post(P + "/request-password-reset", json={"email": "legacy@example.com"})
    assert recovery.status_code == 200, recovery.text


def test_production_rejects_disabled_registration_domain():
    with pytest.raises(ValueError, match="university registration email domain"):
        Settings(environment="production", registration_email_domain="", _env_file=None)
