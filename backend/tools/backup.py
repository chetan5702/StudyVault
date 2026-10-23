"""Create a self-contained SQLite and upload backup for StudyVault.

Stop the web and reminder worker before running this command so the database
snapshot and copied upload files describe the same point in time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import get_settings


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_sqlite_backup(
    database_path: Path,
    upload_dir: Path,
    destination_dir: Path,
    *,
    created_at: datetime | None = None,
) -> Path:
    database_path = database_path.resolve()
    upload_dir = upload_dir.resolve()
    destination_dir = destination_dir.resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {database_path}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    archive = destination_dir / f"studyvault-{timestamp:%Y%m%dT%H%M%SZ}.zip"
    if archive.exists():
        raise FileExistsError(f"Backup already exists: {archive}")

    with tempfile.TemporaryDirectory(prefix="studyvault-backup-") as temporary:
        snapshot = Path(temporary) / "studyvault.db"
        with (
            closing(sqlite3.connect(database_path)) as source,
            closing(sqlite3.connect(snapshot)) as target,
        ):
            source.backup(target)
        with closing(sqlite3.connect(snapshot)) as connection:
            row = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
            revision = row[0] if row else None

        uploads: list[dict[str, str | int]] = []
        upload_files = (
            sorted(path for path in upload_dir.rglob("*") if path.is_file())
            if upload_dir.is_dir()
            else []
        )
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(snapshot, "database/studyvault.db")
            for path in upload_files:
                relative = path.relative_to(upload_dir)
                archive_name = Path("uploads") / relative
                bundle.write(path, archive_name.as_posix())
                uploads.append(
                    {
                        "path": relative.as_posix(),
                        "size_bytes": path.stat().st_size,
                        "sha256": file_digest(path),
                    }
                )
            manifest = {
                "created_at": timestamp.isoformat(),
                "alembic_revision": revision,
                "database_sha256": file_digest(snapshot),
                "upload_count": len(uploads),
                "uploads": uploads,
            }
            bundle.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up StudyVault SQLite data and uploads")
    parser.add_argument("--destination", default="./backups", help="Directory for the ZIP file")
    args = parser.parse_args()
    settings = get_settings()
    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        raise SystemExit(
            "This command supports file-based SQLite. For PostgreSQL, use pg_dump and back up "
            "UPLOAD_DIR during the same maintenance window."
        )
    archive = create_sqlite_backup(
        Path(url.database), Path(settings.upload_dir), Path(args.destination)
    )
    print(f"Backup created: {archive}")


if __name__ == "__main__":
    main()
