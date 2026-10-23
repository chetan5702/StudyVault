"""Validate StudyVault production configuration and persistent services."""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.engine.url import URL
from sqlalchemy.pool import NullPool

from app import database as _database  # noqa: F401  # registers SQLite FK enforcement
from app.config import Settings, get_settings


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def expected_database_revision() -> str:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    return ScriptDirectory.from_config(config).get_current_head()


def safe_database_location(url: URL) -> str:
    if url.drivername.startswith("sqlite"):
        return "SQLite file"
    return f"{url.drivername} database"


def run_deployment_checks(
    settings: Settings, *, expected_revision: str | None = None
) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.append(
        CheckResult(
            "environment",
            settings.environment == "production",
            "ENVIRONMENT is production"
            if settings.environment == "production"
            else "Set ENVIRONMENT=production for a public deployment",
        )
    )
    backend_url = make_url(settings.database_url)
    is_postgres = backend_url.drivername.startswith("postgresql")
    results.append(
        CheckResult(
            "database backend",
            is_postgres,
            "PostgreSQL configured" if is_postgres else "Use PostgreSQL for public deployment",
        )
    )
    results.append(
        CheckResult(
            "public auth limits",
            settings.public_auth_limit_enabled,
            "Database-backed public auth limiting enabled"
            if settings.public_auth_limit_enabled else "Enable PUBLIC_AUTH_LIMIT_ENABLED",
        )
    )
    results.append(
        CheckResult(
            "storage limits",
            settings.max_user_storage_bytes >= settings.max_upload_size_bytes,
            "Cumulative quota accepts at least one maximum-sized upload",
        )
    )

    origins = settings.cors_origins_list
    invalid_origins = []
    for origin in origins:
        parsed = urlparse(origin)
        if (
            origin == "*"
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
        ):
            invalid_origins.append(origin)
    results.append(
        CheckResult(
            "CORS origins",
            not invalid_origins,
            "Origins are empty or explicit public HTTPS origins"
            if not invalid_origins
            else "Replace unsafe origins: " + ", ".join(invalid_origins),
        )
    )
    results.append(
        CheckResult(
            "account email",
            settings.require_email_verification and settings.email_available,
            "Verified-email delivery is configured"
            if settings.require_email_verification and settings.email_available
            else "Enable email verification and configure the production email provider",
        )
    )

    upload_dir = Path(settings.upload_dir).resolve()
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".studyvault-write-check-", dir=upload_dir):
            pass
    except OSError as exc:
        results.append(
            CheckResult("upload storage", False, f"Upload directory is not writable: {exc}")
        )
    else:
        results.append(CheckResult("upload storage", True, "Upload directory is writable"))

    database_url = make_url(settings.database_url)
    engine = create_engine(
        database_url,
        poolclass=NullPool,
        connect_args={"check_same_thread": False, "timeout": 30}
        if database_url.drivername.startswith("sqlite")
        else {},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            head = expected_revision or expected_database_revision()
            results.append(
                CheckResult(
                    "database migration",
                    revision == head,
                    f"Database is at {head}"
                    if revision == head
                    else f"Database revision is {revision or 'missing'}; expected {head}",
                )
            )
            if database_url.drivername.startswith("sqlite"):
                foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
                results.append(
                    CheckResult(
                        "SQLite foreign keys",
                        foreign_keys == 1,
                        "Foreign-key enforcement is enabled"
                        if foreign_keys == 1
                        else "Foreign-key enforcement is disabled",
                    )
                )
        results.append(
            CheckResult(
                "database connection", True, f"Connected to {safe_database_location(database_url)}"
            )
        )
    except Exception as exc:
        results.append(CheckResult("database connection", False, f"Database check failed: {exc}"))
    finally:
        engine.dispose()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Check StudyVault production readiness")
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    args = parser.parse_args()
    try:
        settings = get_settings()
        results = run_deployment_checks(settings)
    except Exception as exc:
        results = [CheckResult("configuration", False, str(exc))]
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            print(f"{'PASS' if result.passed else 'FAIL'} {result.name}: {result.detail}")
    if not all(result.passed for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
