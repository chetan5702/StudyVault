import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "colleges",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column("name", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("city", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column("email", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column(
            "password_hash",
            sa.String(),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column("full_name", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("is_active", sa.Boolean(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "class_groups",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column("name", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column(
            "owner_id",
            sa.String(),
            sa.ForeignKey("users.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column("invite_code", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("description", sa.Text(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_index("ix_class_groups_invite_code", "class_groups", ["invite_code"], unique=True)
    op.create_table(
        "courses",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column(
            "college_id",
            sa.String(),
            sa.ForeignKey("colleges.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column("name", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("degree", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_table(
        "class_members",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column(
            "group_id",
            sa.String(),
            sa.ForeignKey("class_groups.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column("role", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id"),
            primary_key=False,
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "college_id",
            sa.String(),
            sa.ForeignKey("colleges.id"),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "course_id",
            sa.String(),
            sa.ForeignKey("courses.id"),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column("academic_year", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column("semester", sa.Integer(), primary_key=False, nullable=True, unique=False),
        sa.Column("section", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column("phone_number", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column("avatar_url", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column("bio", sa.Text(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_table(
        "subjects",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column(
            "course_id",
            sa.String(),
            sa.ForeignKey("courses.id"),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column("code", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("name", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("semester", sa.Integer(), primary_key=False, nullable=True, unique=False),
        sa.Column("color", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_table(
        "exams",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column(
            "subject_id",
            sa.String(),
            sa.ForeignKey("subjects.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column(
            "group_id",
            sa.String(),
            sa.ForeignKey("class_groups.id"),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column("title", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("exam_type", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "scheduled_for",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column("location", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "reminder_minutes",
            sa.Integer(),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_table(
        "study_tasks",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column(
            "subject_id",
            sa.String(),
            sa.ForeignKey("subjects.id"),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column("title", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("description", sa.Text(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "due_date",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column("completed", sa.Boolean(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_table(
        "units",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column(
            "subject_id",
            sa.String(),
            sa.ForeignKey("subjects.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column("name", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("order_index", sa.Integer(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_table(
        "materials",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column(
            "subject_id",
            sa.String(),
            sa.ForeignKey("subjects.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column(
            "unit_id",
            sa.String(),
            sa.ForeignKey("units.id"),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "group_id",
            sa.String(),
            sa.ForeignKey("class_groups.id"),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column("title", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("description", sa.Text(), primary_key=False, nullable=True, unique=False),
        sa.Column("file_name", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("storage_key", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("mime_type", sa.String(), primary_key=False, nullable=False, unique=False),
        sa.Column("size_bytes", sa.Integer(), primary_key=False, nullable=True, unique=False),
        sa.Column("category", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column("visibility", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_table(
        "reminders",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column(
            "exam_id",
            sa.String(),
            sa.ForeignKey("exams.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column(
            "notify_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column("channel", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column("sent", sa.Boolean(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "delivery_status",
            sa.String(),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )
    op.create_table(
        "material_reports",
        sa.Column("id", sa.String(), primary_key=True, nullable=False, unique=False),
        sa.Column(
            "material_id",
            sa.String(),
            sa.ForeignKey("materials.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column(
            "reporter_id",
            sa.String(),
            sa.ForeignKey("users.id"),
            primary_key=False,
            nullable=False,
            unique=False,
        ),
        sa.Column("reason", sa.Text(), primary_key=False, nullable=False, unique=False),
        sa.Column("status", sa.String(), primary_key=False, nullable=True, unique=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            primary_key=False,
            nullable=True,
            unique=False,
        ),
    )


def downgrade():
    op.drop_table("material_reports")
    op.drop_table("reminders")
    op.drop_table("materials")
    op.drop_table("units")
    op.drop_table("study_tasks")
    op.drop_table("exams")
    op.drop_table("subjects")
    op.drop_table("profiles")
    op.drop_table("class_members")
    op.drop_table("courses")
    op.drop_table("class_groups")
    op.drop_table("users")
    op.drop_table("colleges")
