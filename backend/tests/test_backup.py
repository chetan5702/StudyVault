import json
import sqlite3
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from tools.backup import create_sqlite_backup


def test_sqlite_backup_contains_snapshot_uploads_and_manifest(tmp_path: Path):
    database = tmp_path / "studyvault.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('0003')")
        connection.execute("CREATE TABLE example (value TEXT NOT NULL)")
        connection.execute("INSERT INTO example VALUES ('preserved')")
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "stored.pdf").write_bytes(b"private bytes")

    archive = create_sqlite_backup(
        database,
        uploads,
        tmp_path / "backups",
        created_at=datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

    assert archive.name == "studyvault-20300102T030405Z.zip"
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == {
            "database/studyvault.db",
            "uploads/stored.pdf",
            "manifest.json",
        }
        assert bundle.read("uploads/stored.pdf") == b"private bytes"
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["alembic_revision"] == "0003"
        assert manifest["upload_count"] == 1
        restored = tmp_path / "restored.db"
        restored.write_bytes(bundle.read("database/studyvault.db"))
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM example").fetchone() == ("preserved",)
