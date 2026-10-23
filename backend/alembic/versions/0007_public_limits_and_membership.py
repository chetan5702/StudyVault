"""Enforce group membership uniqueness and persist public API throttling.

Existing duplicates are deduplicated deterministically: an owner record is
retained when present; otherwise the earliest membership is retained.
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_public_limits_and_membership"
down_revision = "0006_archived_exam_subjects"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Alembic defaults to VARCHAR(32), but this revision identifier is 33
    # characters. Widen the version column before Alembic records the revision.
    # SQLite does not enforce VARCHAR lengths and needs no change.
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=64),
            existing_nullable=False,
        )
    rows = bind.execute(sa.text(
        "SELECT id, group_id, user_id, role FROM class_members ORDER BY group_id, user_id, joined_at, id"
    )).all()
    retain = {}
    duplicates = []
    for member_id, group_id, user_id, role in rows:
        key = (group_id, user_id)
        if key not in retain:
            retain[key] = (member_id, role)
        elif role == "owner" and retain[key][1] != "owner":
            duplicates.append(retain[key][0])
            retain[key] = (member_id, role)
        else:
            duplicates.append(member_id)
    for member_id in duplicates:
        bind.execute(sa.text("DELETE FROM class_members WHERE id=:member_id"), {"member_id": member_id})
    with op.batch_alter_table("class_members") as batch:
        batch.create_unique_constraint("uq_class_members_group_user", ["group_id", "user_id"])
    op.create_table(
        "public_rate_limits",
        sa.Column("key_hash", sa.String(length=64), primary_key=True),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("hits >= 0", name="ck_public_rate_limits_nonnegative"),
    )
    op.create_index("ix_public_rate_limits_updated_at", "public_rate_limits", ["updated_at"])


def downgrade():
    op.drop_index("ix_public_rate_limits_updated_at", table_name="public_rate_limits")
    op.drop_table("public_rate_limits")
    with op.batch_alter_table("class_members") as batch:
        batch.drop_constraint("uq_class_members_group_user", type_="unique")
