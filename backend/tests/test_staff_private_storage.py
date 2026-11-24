"""Storage failure safety with synthetic staff and mocked S3; no cloud writes."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import object_storage
from app.api.v1 import staff
from app.database import SessionLocal
from app.models import AcademicResource, StaffRole, UserStorageUsage
from tests.test_staff_publishing import account, academic_programs, admin_credential

API = "/api/v1"


def setup_staff(client):
    course_id, _ = academic_programs()
    _, admin = admin_credential(client)
    faculty_id, faculty = account(
        client, "Synthetic S3 Faculty", "fictional-storage-teacher@suh.edu.in"
    )
    subject = client.post(API + "/staff/subjects", headers=admin, json={
        "course_id": course_id,
        "semester": 3,
        "code": "STOR301",
        "name": "Private Storage Testing",
    })
    assert subject.status_code == 201, subject.text
    subject_id = subject.json()["id"]
    assert client.post(API + "/staff/faculty", headers=admin, json={
        "user_id": faculty_id,
    }).status_code == 201
    assert client.post(API + "/staff/assignments", headers=admin, json={
        "faculty_id": faculty_id,
        "subject_id": subject_id,
    }).status_code == 201
    return faculty_id, faculty, subject_id


def test_faculty_s3_upload_has_private_key_and_no_public_object_url(
    client, pdf, monkeypatch
):
    faculty_id, faculty, subject_id = setup_staff(client)
    client_mock = MagicMock()
    client_mock.get_object.return_value = {
        "Body": SimpleNamespace(
            iter_chunks=lambda chunk_size: iter((pdf,)),
            close=lambda: None,
        ),
    }
    monkeypatch.setattr(object_storage, "_s3_client", lambda: client_mock)
    monkeypatch.setattr(
        object_storage, "get_settings",
        lambda: SimpleNamespace(storage_backend="s3", s3_bucket="fake-private"),
    )
    monkeypatch.setattr(
        staff, "get_settings",
        lambda: SimpleNamespace(storage_backend="s3"),
    )
    response = client.post(
        API + "/staff/resources/upload",
        headers=faculty,
        params={"subject_id": subject_id, "title": "Private fictional PDF"},
        files={"file": ("course.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["is_published"] is False
    assert "storage_key" not in item and "url" not in item
    call = client_mock.put_object.call_args.kwargs
    assert call["Bucket"] == "fake-private"
    assert call["Key"].startswith(f"academic/{faculty_id}/")
    assert call["ContentType"] == "application/pdf"
    assert not call["Key"].startswith("/")
    with SessionLocal() as db:
        record = db.get(AcademicResource, item["id"])
        assert record.storage_key == "s3:" + call["Key"]
        assert record.url is None
        assert db.get(UserStorageUsage, faculty_id).used_bytes == len(pdf)

    deleted = client.delete(
        API + "/staff/resources/" + item["id"], headers=faculty
    )
    assert deleted.status_code == 204
    client_mock.delete_object.assert_called_once_with(
        Bucket="fake-private", Key=call["Key"]
    )
    with SessionLocal() as db:
        assert db.get(AcademicResource, item["id"]) is None
        assert db.get(UserStorageUsage, faculty_id).used_bytes == 0


def test_faculty_s3_database_failure_cleans_up_uploaded_object(
    client, pdf, monkeypatch
):
    faculty_id, faculty, subject_id = setup_staff(client)
    client_mock = MagicMock()
    monkeypatch.setattr(object_storage, "_s3_client", lambda: client_mock)
    monkeypatch.setattr(
        object_storage, "get_settings",
        lambda: SimpleNamespace(storage_backend="s3", s3_bucket="fake-private"),
    )
    monkeypatch.setattr(
        staff, "get_settings",
        lambda: SimpleNamespace(storage_backend="s3"),
    )

    def failed_audit(*args, **kwargs):
        raise RuntimeError("Synthetic failure after private object upload")

    monkeypatch.setattr(staff, "audit", failed_audit)
    with pytest.raises(RuntimeError, match="Synthetic failure"):
        client.post(
            API + "/staff/resources/upload",
            headers=faculty,
            params={"subject_id": subject_id, "title": "Rolled back"},
            files={"file": ("failure.pdf", pdf, "application/pdf")},
        )
    key = client_mock.put_object.call_args.kwargs["Key"]
    client_mock.delete_object.assert_called_once_with(
        Bucket="fake-private", Key=key
    )
    with SessionLocal() as db:
        assert db.query(AcademicResource).filter_by(
            title="Rolled back"
        ).count() == 0
        assert db.get(UserStorageUsage, faculty_id).used_bytes == 0


def test_regular_student_cannot_promote_staff_role(client):
    _, admin_headers = account(
        client, "Fictional Ordinary", "fictional-no-bootstrap@suh.edu.in"
    )
    for endpoint in ("/staff/faculty", "/staff/assignments", "/staff/subjects"):
        assert client.post(
            API + endpoint, headers=admin_headers, json={}
        ).status_code in (403, 422)
    with SessionLocal() as db:
        assert db.query(StaffRole).count() == 0
