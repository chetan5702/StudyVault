import sqlite3
from pathlib import Path

from app.config import Settings
from tools.deployment_check import run_deployment_checks


def production_settings(tmp_path: Path, **changes) -> Settings:
    values = {
        "environment": "production",
        "registration_email_domain": "suh.edu.in",
        "secret_key": "secure-random-production-secret-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "database_url": "sqlite:///" + (tmp_path / "production.db").as_posix(),
        "upload_dir": str(tmp_path / "uploads"),
        "require_email_verification": True,
        "public_frontend_url": "https://studyvault.example",
        "email_provider": "resend",
        "resend_api_key": "test-provider-key",
        "email_from": "StudyVault <noreply@studyvault.example>",
        "cors_origins": "https://studyvault.example",
        "_env_file": None,
    }
    values.update(changes)
    return Settings(**values)


def test_deployment_check_validates_services_without_exposing_secrets(tmp_path: Path):
    settings = production_settings(tmp_path)
    database = tmp_path / "production.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('test-head')")

    results = run_deployment_checks(settings, expected_revision="test-head")

    # SQLite is supported for local/test environments, but not approved by
    # the production preflight after the production hardening changes.
    assert all(result.passed for result in results if result.name != "database backend"), results
    assert not next(result for result in results if result.name == "database backend").passed
    rendered = " ".join(result.detail for result in results)
    assert settings.secret_key not in rendered
    assert settings.resend_api_key not in rendered


def test_deployment_check_rejects_unsafe_cors_and_impossible_quota(tmp_path: Path):
    settings = production_settings(
        tmp_path,
        cors_origins="*,http://localhost:5173",
        max_upload_size_bytes=20,
        max_user_storage_bytes=10,
    )
    database = tmp_path / "production.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('test-head')")

    results = run_deployment_checks(settings, expected_revision="test-head")
    failures = {result.name for result in results if not result.passed}

    assert failures == {"database backend", "storage limits", "CORS origins"}
