"""Private S3-compatible storage for validated StudyVault uploads.

The database owns access control. Never expose a public bucket or issue a
direct object URL to an unauthenticated client. The s3: prefix distinguishes
new object keys from legacy local files without a schema migration.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.config import get_settings
from app.storage import get_file_path

logger = logging.getLogger(__name__)
S3_PREFIX = "s3:"


@lru_cache(maxsize=1)
def _s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 2},
        ),
    )


def upload_validated_file(path: Path, key: str, mime_type: str) -> str:
    """Persist only after the upload has passed content validation and quota checks."""
    settings = get_settings()
    if settings.storage_backend == "local":
        return key
    try:
        with path.open("rb") as content:
            _s3_client().put_object(
                Bucket=settings.s3_bucket,
                Key=key,
                Body=content,
                ContentType=mime_type,
            )
        return S3_PREFIX + key
    except (BotoCoreError, ClientError, OSError):
        logger.exception("Object storage upload failed")
        raise HTTPException(503, "File storage is temporarily unavailable") from None


def download_stored_file(storage_key: str, filename: str, mime_type: str):
    """Return a private authenticated download; don't redirect to the object store."""
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }
    if not storage_key.startswith(S3_PREFIX):
        path = get_file_path(storage_key)
        if not path.is_file():
            raise HTTPException(404, "Stored file not found")
        return FileResponse(path, filename=filename, media_type=mime_type, headers=headers)

    try:
        result = _s3_client().get_object(
            Bucket=get_settings().s3_bucket, Key=storage_key[len(S3_PREFIX):]
        )
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code")) in {"NoSuchKey", "404", "NotFound"}:
            raise HTTPException(404, "Stored file not found") from exc
        logger.exception("Object storage download failed")
        raise HTTPException(503, "File storage is temporarily unavailable") from None
    except BotoCoreError:
        logger.exception("Object storage download failed")
        raise HTTPException(503, "File storage is temporarily unavailable") from None

    content = result["Body"]

    def chunks():
        try:
            for chunk in content.iter_chunks(chunk_size=65536):
                if chunk:
                    yield chunk
        finally:
            content.close()

    headers["Content-Disposition"] = "attachment; filename*=UTF-8''" + quote(filename, safe="")
    return StreamingResponse(chunks(), media_type=mime_type, headers=headers)


def delete_stored_file(storage_key: str) -> None:
    if not storage_key.startswith(S3_PREFIX):
        get_file_path(storage_key).unlink(missing_ok=True)
        return
    try:
        _s3_client().delete_object(
            Bucket=get_settings().s3_bucket, Key=storage_key[len(S3_PREFIX):]
        )
    except (BotoCoreError, ClientError):
        logger.exception("Object storage deletion failed")
        raise HTTPException(503, "File storage is temporarily unavailable") from None
