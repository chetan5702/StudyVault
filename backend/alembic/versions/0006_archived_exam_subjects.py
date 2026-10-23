"""Preserve archived exams when their former subject is deleted.

Revision ID: 0006_archived_exam_subjects
Revises: 0005_account_security

Exam deletion is intentionally a soft delete because reminders and delivered
notifications form an audit history. A later subject deletion therefore clears
the archived exam's foreign key and retains immutable subject code/name
snapshots instead of deleting any exam, reminder, or notification rows.
"""

import sqlalchemy as sa

from alembic import op

revision = "0006_archived_exam_subjects"
down_revision = "0005_account_security"
branch_labels = None
depends_on = None


def _prepare_sqlite_batch(bind) -> bool:
    """Allow SQLite to rebuild a table referenced by reminder history."""
    if bind.dialect.name != "sqlite":
        return False
    bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    if bind.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 0:
        raise RuntimeError("Could not suspend SQLite foreign-key checks for table migration")
    return True


def _finish_sqlite_batch(bind, sqlite_batch: bool) -> None:
    if not sqlite_batch:
        return
    violations = bind.exec_driver_sql("PRAGMA foreign_key_check").all()
    if violations:
        raise RuntimeError(f"Foreign-key violations after exam migration: {violations!r}")
    # SQLite ignores changes to this pragma until the current migration unit
    # commits. Alembic closes this short-lived connection after recording the
    # revision; every later application connection enables the pragma through
    # app.database's Engine connect listener.
    bind.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade():
    bind = op.get_bind()
    sqlite_batch = _prepare_sqlite_batch(bind)
    op.add_column("exams", sa.Column("subject_code_snapshot", sa.String(), nullable=True))
    op.add_column("exams", sa.Column("subject_name_snapshot", sa.String(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE exams SET "
            "subject_code_snapshot = (SELECT code FROM subjects WHERE subjects.id = exams.subject_id), "
            "subject_name_snapshot = (SELECT name FROM subjects WHERE subjects.id = exams.subject_id)"
        )
    )
    with op.batch_alter_table("exams") as batch_op:
        batch_op.alter_column(
            "subject_id",
            existing_type=sa.String(),
            nullable=True,
        )
        batch_op.alter_column(
            "subject_code_snapshot",
            existing_type=sa.String(),
            nullable=False,
        )
        batch_op.alter_column(
            "subject_name_snapshot",
            existing_type=sa.String(),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_exams_subject_or_archived",
            "subject_id IS NOT NULL OR deleted_at IS NOT NULL",
        )
    _finish_sqlite_batch(bind, sqlite_batch)


def downgrade():
    bind = op.get_bind()
    detached_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM exams WHERE subject_id IS NULL")
    ).scalar_one()
    if detached_count:
        raise RuntimeError(
            "Cannot downgrade while archived exams reference deleted subjects; "
            "restore those subjects or remove the archived exams first."
        )
    sqlite_batch = _prepare_sqlite_batch(bind)
    with op.batch_alter_table("exams") as batch_op:
        batch_op.drop_constraint("ck_exams_subject_or_archived", type_="check")
        batch_op.alter_column(
            "subject_id",
            existing_type=sa.String(),
            nullable=False,
        )
        batch_op.drop_column("subject_name_snapshot")
        batch_op.drop_column("subject_code_snapshot")
    _finish_sqlite_batch(bind, sqlite_batch)
