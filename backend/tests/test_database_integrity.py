import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine
from app.models import Unit


def sqlite_foreign_keys_enabled(sqlalchemy_engine) -> bool:
    with sqlalchemy_engine.connect() as connection:
        return connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


def test_every_sqlite_engine_connection_enables_foreign_keys():
    assert sqlite_foreign_keys_enabled(engine)

    independent_engine = create_engine("sqlite://")
    try:
        assert sqlite_foreign_keys_enabled(independent_engine)
    finally:
        independent_engine.dispose()


def test_sqlite_rejects_orphaned_foreign_key():
    with SessionLocal() as db:
        db.add(Unit(subject_id="missing-subject", name="Orphaned unit"))
        with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
            db.commit()
