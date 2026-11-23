"""Private faculty uploads and tightly-scoped administrative permissions.

Non-destructive: no staff roles or assignments are granted automatically.
Old academic links remain valid; new faculty files have a NULL URL and
private storage key. Never run a down migration while uploaded official
files exist.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_faculty_admin_publishing"
down_revision = "0009_verified_enrollments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "staff_roles",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'faculty')", name="ck_staff_roles_allowed"),
    )
    op.create_table(
        "teaching_assignments",
        sa.Column("faculty_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("subject_id", sa.String(), sa.ForeignKey("academic_subjects.id"), primary_key=True),
        sa.Column("assigned_by_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "staff_audit_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("actor_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("academic_resources") as batch:
        batch.alter_column(
            "url", existing_type=sa.String(2048), nullable=True
        )
        batch.add_column(sa.Column("storage_key", sa.String(), nullable=True))
        batch.add_column(sa.Column("file_name", sa.String(200), nullable=True))
        batch.add_column(sa.Column("mime_type", sa.String(200), nullable=True))
        batch.add_column(sa.Column("size_bytes", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("uploaded_by_id", sa.String(), nullable=True))
        batch.create_foreign_key(
            "fk_academic_resources_uploaded_by_id_users",
            "users", ["uploaded_by_id"], ["id"]
        )


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text(
        "SELECT 1 FROM academic_resources WHERE url IS NULL OR storage_key IS NOT NULL LIMIT 1"
    )).first():
        raise RuntimeError(
            "Cannot downgrade faculty file schema while private faculty uploads exist; "
            "back up and explicitly migrate or remove those files first"
        )
    with op.batch_alter_table("academic_resources") as batch:
        batch.drop_constraint(
            "fk_academic_resources_uploaded_by_id_users", type_="foreignkey"
        )
        batch.drop_column("uploaded_by_id")
        batch.drop_column("size_bytes")
        batch.drop_column("mime_type")
        batch.drop_column("file_name")
        batch.drop_column("storage_key")
        batch.alter_column("url", existing_type=sa.String(2048), nullable=False)
    op.drop_table("staff_audit_events")
    op.drop_table("teaching_assignments")
    op.drop_table("staff_roles")
