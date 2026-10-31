"""Opt-in live S3 check: tests only a random disposable key.

Run from the backend directory with real private S3 environment credentials:
    STUDYVAULT_STORAGE_PROBE=1 python -m tools.storage_integration_check

The command never prints credentials or signed URLs. It deletes its test
object on both success and failure, without accessing actual student files.
"""
from __future__ import annotations

import json
import os
import uuid
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

from botocore.exceptions import ClientError

from app.config import get_settings
from app.object_storage import _s3_client


def run_probe() -> dict[str, bool]:
    if os.getenv("STUDYVAULT_STORAGE_PROBE") != "1":
        raise RuntimeError("Explicit opt-in required: STUDYVAULT_STORAGE_PROBE=1")

    settings = get_settings()
    if settings.storage_backend != "s3":
        raise RuntimeError("Set STORAGE_BACKEND=s3 and S3 credentials before running")

    bucket = settings.s3_bucket
    key = "__studyvault_integration__/" + uuid.uuid4().hex + ".txt"
    expected = b"StudyVault temporary object storage verification"
    client = _s3_client()
    result = {
        "private_anonymous_read_denied": False,
        "upload": False,
        "download_matches": False,
        "delete": False,
        "missing_after_delete": False,
    }
    try:
        public_url = (
            settings.s3_endpoint_url.rstrip("/")
            + "/"
            + quote(bucket, safe="")
            + "/"
            + quote(key, safe="/")
        )
        try:
            with urlopen(public_url, timeout=15) as response:
                result["private_anonymous_read_denied"] = response.status == 403
        except HTTPError as exc:
            result["private_anonymous_read_denied"] = exc.code == 403

        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=expected,
            ContentType="text/plain",
        )
        result["upload"] = True

        response = client.get_object(Bucket=bucket, Key=key)
        try:
            result["download_matches"] = response["Body"].read() == expected
        finally:
            response["Body"].close()

        client.delete_object(Bucket=bucket, Key=key)
        result["delete"] = True

        try:
            response = client.get_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            result["missing_after_delete"] = str(
                exc.response.get("Error", {}).get("Code")
            ) in {"NoSuchKey", "404", "NotFound"}
        else:
            response["Body"].close()
    finally:
        # Use a unique disposable prefix; cleanup only our own key.
        try:
            client.delete_object(Bucket=bucket, Key=key)
        except Exception:
            # Operator must inspect the __studyvault_integration__ prefix on failure.
            pass
    return result


def main() -> None:
    result = run_probe()
    print(json.dumps(result, sort_keys=True))
    if not all(result.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
