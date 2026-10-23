from datetime import timedelta
from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

from app.database import SessionLocal
from app.models import ClassMember
from app.security import create_access_token
from app.storage import ensure_storage, get_file_path, settings
from tests.test_workflow import P, second, subject, upload


def test_material_limit_matches_backend_configuration(client, student, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_bytes", 123456)
    monkeypatch.setattr(settings, "max_user_storage_bytes", 654321)
    assert client.get(P + "/materials/config").status_code == 401
    response = client.get(P + "/materials/config", headers=student)
    assert response.status_code == 200
    assert response.json() == {
        "max_upload_size_bytes": 123456,
        "max_user_storage_bytes": 654321,
        "used_storage_bytes": 0,
        "remaining_storage_bytes": 654321,
    }


def test_real_contents_override_browser_mime(client, student, pdf):
    sid = subject(client, student)
    response = client.post(
        P + "/materials/upload",
        headers=student,
        params={"subject_id": sid, "title": "Actual PDF"},
        files={"file": ("unsafe.exe", pdf, "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["mime_type"] == "application/pdf"
    assert response.json()["size_bytes"] == len(pdf)
    assert all(
        p.name.endswith(".pdf") and "unsafe" not in p.name for p in ensure_storage().iterdir()
    )


@pytest.mark.parametrize("format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_image_contents(client, student, format, mime):
    stream = BytesIO()
    Image.new("RGB", (10, 10)).save(stream, format=format)
    response = upload(client, student, subject(client, student), stream.getvalue())
    assert response.status_code == 201
    assert response.json()["mime_type"] == mime


def test_expired_token(client, student):
    me = client.get(P + "/auth/me", headers=student).json()
    token = create_access_token(me["id"], me["email"], me["full_name"], timedelta(seconds=-5))
    assert (
        client.get(P + "/subjects", headers={"Authorization": "Bearer " + token}).status_code == 401
    )


def test_naive_exam_rejected(client, student):
    response = client.post(
        P + "/exams",
        headers=student,
        json={
            "subject_id": subject(client, student),
            "title": "Exam",
            "scheduled_for": "2026-12-01T12:00:00",
        },
    )
    assert response.status_code == 422


def test_group_access_removed_immediately(client, student, pdf):
    sid = subject(client, student)
    group = client.post(P + "/groups", headers=student, json={"name": "Group"}).json()
    other = second(client)
    client.post(P + "/groups/join", headers=other, params={"invite_code": group["invite_code"]})
    material = upload(client, student, sid, pdf, visibility="group", group_id=group["id"]).json()
    other_id = client.get(P + "/auth/me", headers=other).json()["id"]
    with SessionLocal() as db:
        membership = db.query(ClassMember).filter_by(user_id=other_id, group_id=group["id"]).one()
        db.delete(membership)
        db.commit()
    assert client.get(P + f"/materials/{material['id']}/download", headers=other).status_code == 404
    assert client.get(P + "/materials", headers=other).json() == []


def test_external_storage_paths_cannot_escape_root(tmp_path):
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"not inside storage")
    assert get_file_path(str(outside)).parent == ensure_storage()


def test_chunked_request_limit(monkeypatch):
    import asyncio

    from app.upload_limit import UploadLimitMiddleware

    monkeypatch.setattr(settings, "max_upload_size_bytes", 10)
    messages = iter(
        [
            {"type": "http.request", "body": b"x" * 65536, "more_body": True},
            {"type": "http.request", "body": b"x" * 11, "more_body": False},
        ]
    )

    async def receive():
        return next(messages)

    async def send(message):
        pass

    async def downstream(scope, receive, send):
        await receive()
        await receive()

    async def run():
        with pytest.raises(HTTPException) as error:
            await UploadLimitMiddleware(downstream)(
                {"type": "http", "path": "/api/v1/materials/upload", "headers": []}, receive, send
            )
        assert error.value.status_code == 413

    asyncio.run(run())
