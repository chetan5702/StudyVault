"""Add exam lifecycle, persistent reminder delivery and private notifications.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Existing tables are altered in place; no existing columns or rows are rewritten.
    op.add_column("exams", sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"))
    op.add_column(
        "exams", sa.Column("reminder_generation", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("exams", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    additions = [
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("offset_minutes", sa.Integer(), nullable=True),
        sa.Column("exam_scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("claim_token", sa.String(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
    ]
    for column in additions:
        op.add_column("reminders", column)
    op.execute(
        sa.text(
            "UPDATE reminders SET user_id = (SELECT user_id FROM exams WHERE exams.id = reminders.exam_id), "
            "exam_scheduled_for = (SELECT scheduled_for FROM exams WHERE exams.id = reminders.exam_id)"
        )
    )
    # Leave legacy offset_minutes null: duplicate legacy records must remain intact.
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index(
        "ix_reminder_due", "reminders", ["delivery_status", "next_attempt_at", "notify_at"]
    )
    op.create_index(
        "uq_reminder_slot",
        "reminders",
        ["exam_id", "generation", "channel", "offset_minutes"],
        unique=True,
    )
    op.create_table(
        "reminder_preferences",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("reminder_minutes", sa.JSON(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "reminder_id", sa.String(), sa.ForeignKey("reminders.id"), nullable=False, unique=True
        ),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("exam_id", sa.String(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_table(
        "reminder_lock",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.execute(sa.text("INSERT INTO reminder_lock (id, version) VALUES (1, 0)"))


def downgrade():
    op.drop_table("notifications")
    op.drop_table("reminder_preferences")
    op.drop_table("reminder_lock")
    op.drop_index("uq_reminder_slot", table_name="reminders")
    op.drop_index("ix_reminder_due", table_name="reminders")
    op.drop_index("ix_reminders_user_id", table_name="reminders")
    for name in (
        "payload",
        "claim_token",
        "last_error",
        "delivered_at",
        "first_attempt_at",
        "next_attempt_at",
        "delivery_attempts",
        "generation",
        "exam_scheduled_for",
        "offset_minutes",
        "user_id",
    ):
        op.drop_column("reminders", name)
    for name in ("deleted_at", "reminder_generation", "timezone"):
        op.drop_column("exams", name)
