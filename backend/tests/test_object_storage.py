"""Focused tests for the optional private object-storage adapter."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app import object_storage


def test_s3_upload_uses_private_bucket(monkeypatch, tmp_path):
    file = tmp_path / "checked.pdf"
    file.write_bytes(b"%PDF-1.7 validated elsewhere")
    client = MagicMock()
    monkeypatch.setattr(object_storage, "_s3_client", lambda: client)
    monkeypatch.setattr(
        object_storage,
        "get_settings",
        lambda: SimpleNamespace(storage_backend="s3", s3_bucket="private"),
    )
    key = object_storage.upload_validated_file(file, "user/uuid.pdf", "application/pdf")
    assert key == "s3:user/uuid.pdf"
    assert client.put_object.call_args.kwargs["Bucket"] == "private"
    assert client.put_object.call_args.kwargs["Key"] == "user/uuid.pdf"


def test_local_upload_preserves_original_key(monkeypatch, tmp_path):
    monkeypatch.setattr(
        object_storage,
        "get_settings",
        lambda: SimpleNamespace(storage_backend="local"),
    )
    assert object_storage.upload_validated_file(tmp_path / "unused", "legacy.pdf", "application/pdf") == "legacy.pdf"


def test_s3_missing_key_is_404(monkeypatch):
    from botocore.exceptions import ClientError

    client = MagicMock()
    client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "No such key"}}, "GetObject"
    )
    monkeypatch.setattr(object_storage, "_s3_client", lambda: client)
    monkeypatch.setattr(
        object_storage, "get_settings", lambda: SimpleNamespace(s3_bucket="private")
    )
    with pytest.raises(HTTPException) as exc:
        object_storage.download_stored_file("s3:missing.pdf", "missing.pdf", "application/pdf")
    assert exc.value.status_code == 404


def test_s3_delete_is_private(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(object_storage, "_s3_client", lambda: client)
    monkeypatch.setattr(
        object_storage, "get_settings", lambda: SimpleNamespace(s3_bucket="private")
    )
    object_storage.delete_stored_file("s3:user/test.pdf")
    client.delete_object.assert_called_once_with(Bucket="private", Key="user/test.pdf")


@pytest.mark.anyio
async def test_private_s3_download_streams_and_closes(monkeypatch):
    from app import object_storage

    closed = []
    body = SimpleNamespace(
        iter_chunks=lambda chunk_size: iter([b"safe", b"-content"]),
        close=lambda: closed.append(True),
    )
    client = MagicMock()
    client.get_object.return_value = {"Body": body}
    monkeypatch.setattr(object_storage, "_s3_client", lambda: client)
    monkeypatch.setattr(
        object_storage, "get_settings", lambda: SimpleNamespace(s3_bucket="private")
    )
    response = object_storage.download_stored_file(
        "s3:user/document.pdf", "report.pdf", "application/pdf"
    )
    chunks = [chunk async for chunk in response.body_iterator]
    assert b"".join(chunks) == b"safe-content"
    assert closed == [True]
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "attachment;" in response.headers["content-disposition"]


def test_s3_upload_failure_is_service_unavailable(monkeypatch, tmp_path):
    from botocore.exceptions import ClientError

    file = tmp_path / "validated.pdf"
    file.write_bytes(b"%PDF-1.7")
    client = MagicMock()
    client.put_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Denied"}}, "PutObject"
    )
    monkeypatch.setattr(object_storage, "_s3_client", lambda: client)
    monkeypatch.setattr(
        object_storage,
        "get_settings",
        lambda: SimpleNamespace(storage_backend="s3", s3_bucket="private"),
    )
    with pytest.raises(HTTPException) as exc:
        object_storage.upload_validated_file(file, "user/file.pdf", "application/pdf")
    assert exc.value.status_code == 503


def test_s3_download_access_denied_does_not_expose_data(monkeypatch):
    from botocore.exceptions import ClientError

    client = MagicMock()
    client.get_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Denied"}}, "GetObject"
    )
    monkeypatch.setattr(object_storage, "_s3_client", lambda: client)
    monkeypatch.setattr(
        object_storage, "get_settings", lambda: SimpleNamespace(s3_bucket="private")
    )
    with pytest.raises(HTTPException) as exc:
        object_storage.download_stored_file(
            "s3:user/private.pdf", "private.pdf", "application/pdf"
        )
    assert exc.value.status_code == 503
    assert "private.pdf" not in exc.value.detail


def test_s3_delete_failure_reports_service_unavailable(monkeypatch):
    from botocore.exceptions import ClientError

    client = MagicMock()
    client.delete_object.side_effect = ClientError(
        {"Error": {"Code": "ServiceUnavailable", "Message": "Retry"}}, "DeleteObject"
    )
    monkeypatch.setattr(object_storage, "_s3_client", lambda: client)
    monkeypatch.setattr(
        object_storage, "get_settings", lambda: SimpleNamespace(s3_bucket="private")
    )
    with pytest.raises(HTTPException) as exc:
        object_storage.delete_stored_file("s3:user/private.pdf")
    assert exc.value.status_code == 503


def test_upload_db_failure_compensates_private_object(monkeypatch, tmp_path):
    from app.api.v1 import materials

    tmp_file = tmp_path / "valid.pdf"
    tmp_file.write_bytes(b"validated file bytes")

    class FakeDb:
        def __init__(self):
            self.rolled_back = False

        def query(self, model):
            return self

        def filter_by(self, **filters):
            return self

        def first(self):
            return object()

        def add(self, value):
            pass

        def flush(self):
            pass

        def refresh(self, value):
            pass

        def commit(self):
            raise RuntimeError("Simulated failed database commit")

        def rollback(self):
            self.rolled_back = True

    class Payload:
        subject_id = "subject"
        unit_id = None
        group_id = None
        visibility = "private"

        def model_dump(self):
            return {"subject_id": "subject", "title": "Test", "visibility": "private"}

    monkeypatch.setattr(
        materials, "save_upload", lambda file: (tmp_file, "file.pdf", "application/pdf", 20)
    )
    monkeypatch.setattr(
        materials,
        "get_settings",
        lambda: SimpleNamespace(storage_backend="s3"),
    )
    monkeypatch.setattr(materials, "reserve_storage", lambda db, user_id, size: None)
    monkeypatch.setattr(
        materials,
        "upload_validated_file",
        lambda path, key, mime: "s3:user/file.pdf",
    )
    removed = []
    monkeypatch.setattr(materials, "delete_stored_file", removed.append)
    db = FakeDb()
    with pytest.raises(RuntimeError, match="failed database commit"):
        materials.upload_material(
            file=SimpleNamespace(filename="file.pdf"),
            payload=Payload(),
            current_user=SimpleNamespace(id="user"),
            db=db,
        )
    assert db.rolled_back
    assert removed == ["s3:user/file.pdf"]
    assert not tmp_file.exists()
