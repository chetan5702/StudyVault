"""Add persistent login throttling and per-user storage accounting.

Revision ID: 0004_security_limits
Revises: 0003
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_security_limits"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "login_attempts",
        sa.Column("identifier_hash", sa.String(length=64), primary_key=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("failed_attempts >= 0", name="ck_login_attempts_nonnegative"),
    )
    op.create_index("ix_login_attempts_updated_at", "login_attempts", ["updated_at"])

    op.create_table(
        "user_storage_usage",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("used_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("used_bytes >= 0", name="ck_user_storage_usage_nonnegative"),
    )

    users = sa.table("users", sa.column("id", sa.String()))
    materials = sa.table(
        "materials",
        sa.column("user_id", sa.String()),
        sa.column("size_bytes", sa.Integer()),
    )
    usage = sa.table(
        "user_storage_usage",
        sa.column("user_id", sa.String()),
        sa.column("used_bytes", sa.BigInteger()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    positive_size = sa.case(
        (materials.c.size_bytes > 0, materials.c.size_bytes),
        else_=0,
    )
    existing_usage = (
        sa.select(
            users.c.id,
            sa.func.coalesce(sa.func.sum(positive_size), 0),
            sa.func.now(),
        )
        .select_from(users.outerjoin(materials, materials.c.user_id == users.c.id))
        .group_by(users.c.id)
    )
    op.get_bind().execute(
        usage.insert().from_select(
            [usage.c.user_id, usage.c.used_bytes, usage.c.updated_at],
            existing_usage,
        )
    )


def downgrade():
    op.drop_table("user_storage_usage")
    op.drop_index("ix_login_attempts_updated_at", table_name="login_attempts")
    op.drop_table("login_attempts")
