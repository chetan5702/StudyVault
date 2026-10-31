"""Focused tests for the optional private object-storage adapter."""
from pathlib import Path
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
