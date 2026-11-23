"""Introduce trusted enrollment independent of self-reported academic profiles.

Existing accounts do NOT receive verified enrollment automatically.
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_verified_enrollments"
down_revision = "0008_academic_cohorts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "verified_enrollments",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("course_id", sa.String(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("academic_session", sa.String(20), nullable=False),
        sa.Column("verification_source", sa.String(20), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("semester BETWEEN 1 AND 8", name="ck_verified_enrollment_semester"),
        sa.CheckConstraint(
            "verification_source IN ('university', 'admin', 'development')",
            name="ck_verified_enrollment_source",
        ),
    )


def downgrade():
    op.drop_table("verified_enrollments")
