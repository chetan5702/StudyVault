from __future__ import annotations

from collections.abc import Generator
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    """Make SQLite enforce the foreign keys declared by the ORM and migrations."""
    if not isinstance(dbapi_connection, SQLiteConnection):
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 30}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Any, Any, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
