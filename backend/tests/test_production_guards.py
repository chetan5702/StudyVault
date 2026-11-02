import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import ClassGroup, ClassMember, PublicRateLimit, User
from app.public_limits import enforce_limit


def test_public_rate_limit_atomic_and_persisted(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'public_auth_limit_enabled', True)
    with SessionLocal() as first:
        enforce_limit(first, '203.0.113.7', 'register', maximum=2, window_seconds=3600)
    with SessionLocal() as second:
        enforce_limit(second, '203.0.113.7', 'register', maximum=2, window_seconds=3600)
    with SessionLocal() as third:
        with pytest.raises(HTTPException) as error:
            enforce_limit(third, '203.0.113.7', 'register', maximum=2, window_seconds=3600)
        assert error.value.status_code == 429
        assert int(error.value.headers['Retry-After']) >= 1
        assert third.query(PublicRateLimit).count() == 1
        assert third.query(PublicRateLimit).first().key_hash != '203.0.113.7'
    with SessionLocal() as db:
        # Different IPs are independently limited.
        enforce_limit(db, '203.0.113.8', 'register', maximum=2, window_seconds=3600)


def test_duplicate_membership_rejected_by_database():
    with SessionLocal() as db:
        user = User(email='member@example.com', full_name='Member', password_hash='not-used')
        db.add(user)
        db.flush()
        group = ClassGroup(name='Class', owner_id=user.id, invite_code='NOREPEAT123')
        db.add(group)
        db.flush()
        db.add(ClassMember(group_id=group.id, user_id=user.id, role='owner'))
        db.commit()
        db.add(ClassMember(group_id=group.id, user_id=user.id, role='member'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.query(ClassMember).count() == 1


def test_production_disallows_public_limit_bypass():
    with pytest.raises(ValueError, match='public authentication rate limiting'):
        Settings(
            environment='production',
            registration_email_domain='suh.edu.in',
            secret_key='unique-source-of-random-data-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
            require_email_verification=True,
            public_frontend_url='https://studyvault.example',
            email_provider='resend', resend_api_key='stub', email_from='StudyVault <example@studyvault.example>',
            public_auth_limit_enabled=False, _env_file=None,
        )
