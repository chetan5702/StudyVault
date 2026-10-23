"""Verify migrations on a copy, preserving every original column and row."""

import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "studyvault.db"
backup = root / "studyvault.pre-reminders.backup"


def rows(path, columns=None):
    with closing(sqlite3.connect(path)) as db:
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('alembic_version','sqlite_sequence')"
            )
        ]
        if columns is None:
            columns = {
                table: [r[1] for r in db.execute(f'PRAGMA table_info("{table}")')]
                for table in tables
            }
        values = {}
        for table, names in columns.items():
            quoted = ", ".join('"' + name.replace('"', '""') + '"' for name in names)
            safe_table = table.replace('"', '""')
            values[table] = sorted(
                db.execute(f'SELECT {quoted} FROM "{safe_table}"').fetchall(), key=repr
            )
        return columns, values


if source.exists():
    columns, before = rows(source)
    if not backup.exists():
        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(backup)) as dst:
            src.backup(dst)
    with tempfile.TemporaryDirectory(prefix="studyvault-adopt-") as temp:
        copied = Path(temp) / "copy.db"
        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(copied)) as dst:
            src.backup(dst)
        result = subprocess.run(
            [sys.executable, "-m", "tools.init_db"],
            cwd=root,
            env={**os.environ, "DATABASE_URL": "sqlite:///" + copied.as_posix()},
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise SystemExit(result.stdout + result.stderr)
        assert before == rows(copied, columns)[1], "Migration changed existing rows"
    result = subprocess.run(
        [sys.executable, "-m", "tools.init_db"],
        cwd=root,
        env={**os.environ, "DATABASE_URL": "sqlite:///" + source.as_posix()},
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.returncode)
    assert before == rows(source, columns)[1], "Existing rows changed during migration"
    print(
        f"All {sum(map(len, before.values()))} existing rows in {len(before)} tables preserved; "
        f"pre-migration backup retained at {backup.name}."
    )
else:
    raise SystemExit("No existing SQLite database found; use tools.init_db for a fresh database.")
