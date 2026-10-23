"""Add verified accounts, revocable JWT versions and one-time account tokens.

Revision ID: 0005_account_security
Revises: 0004_security_limits
"""

import sqlalchemy as sa

from alembic import op

revision = "0005_account_security"
down_revision = "0004_security_limits"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    # Existing accounts predate verification and must retain their current access.
    op.execute(sa.text("UPDATE users SET email_verified_at = CURRENT_TIMESTAMP"))

    op.create_table(
        "account_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_account_tokens_purpose",
        ),
    )
    op.create_index(
        "ix_account_tokens_token_digest", "account_tokens", ["token_digest"], unique=True
    )
    op.create_index(
        "ix_account_tokens_user_purpose_created",
        "account_tokens",
        ["user_id", "purpose", "created_at"],
    )


def downgrade():
    op.drop_index("ix_account_tokens_user_purpose_created", table_name="account_tokens")
    op.drop_index("ix_account_tokens_token_digest", table_name="account_tokens")
    op.drop_table("account_tokens")
    op.drop_column("users", "token_version")
    op.drop_column("users", "email_verified_at")
