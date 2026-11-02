import os
import tempfile
from pathlib import Path

import pytest

_root = tempfile.TemporaryDirectory(prefix="studyvault-tests-")
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_root.name) / "isolated.db").as_posix()
os.environ["UPLOAD_DIR"] = str(Path(_root.name) / "uploads")
os.environ["SEED_DEMO"] = "false"
os.environ["SECRET_KEY"] = "test-only-secret-never-for-deployment"
os.environ["STUDYVAULT_DEBUG"] = "false"
# Tests must never inherit a configured external email provider from .env.
os.environ["EMAIL_PROVIDER"] = "disabled"
os.environ["RESEND_API_KEY"] = ""
os.environ["EMAIL_FROM"] = ""
os.environ["EMAIL_SINK_DIR"] = str(Path(_root.name) / "email-sink")
os.environ["REQUIRE_EMAIL_VERIFICATION"] = "false"
os.environ["REGISTRATION_EMAIL_DOMAIN"] = ""
os.environ["PUBLIC_FRONTEND_URL"] = "http://localhost:5173"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def close_engine():
    yield
    engine.dispose()
    _root.cleanup()


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    from app.storage import ensure_storage

    for path in ensure_storage().iterdir():
        path.unlink()


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def student(client):
    result = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Student One",
            "email": "one@example.com",
            "password": "Password123!",
        },
    ).json()
    return {"Authorization": "Bearer " + result["access_token"]}


@pytest.fixture
def pdf():
    from io import BytesIO

    from pypdf import PdfWriter

    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(stream)
    return stream.getvalue()
