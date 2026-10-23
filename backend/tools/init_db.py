"""Migrate a fresh database or safely adopt the original create_all schema."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, create_engine, inspect

from alembic import command
from app.database import engine

config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
with engine.connect() as connection:
    tables = set(inspect(connection).get_table_names())
    legacy = (
        bool(tables - {"alembic_version"})
        and not MigrationContext.configure(connection).get_current_heads()
    )
    if legacy:
        # Compare against the immutable original revision, not today's evolving ORM.
        baseline_engine = create_engine("sqlite://")
        baseline_metadata = MetaData()
        baseline_path = (
            Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0001_initial.py"
        )
        spec = spec_from_file_location("studyvault_baseline", baseline_path)
        baseline = module_from_spec(spec)
        spec.loader.exec_module(baseline)
        with baseline_engine.begin() as baseline_connection:
            with Operations.context(MigrationContext.configure(baseline_connection)):
                baseline.upgrade()
            baseline_metadata.reflect(baseline_connection)
        baseline_engine.dispose()
        differences = compare_metadata(MigrationContext.configure(connection), baseline_metadata)
        if differences:
            raise SystemExit(
                "Existing database differs from baseline; refusing to stamp. Back up and reconcile the schema first.\n"
                + str(differences)
            )
if legacy:
    command.stamp(config, "0001")
command.upgrade(config, "head")
engine.dispose()
print("Database is at Alembic head. Existing rows are preserved.")
