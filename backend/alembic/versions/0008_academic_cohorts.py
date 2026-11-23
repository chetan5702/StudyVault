"""Add department/branch academic hierarchy and curated semester library.

Existing users, profiles, subjects, materials, and exam records are preserved.
All existing branch mappings remain unverified and are not assigned automatically.
Officially listed SUH B.Tech CSE specializations are seeded as catalog options;
email subdomains are intentionally NOT associated with branch IDs.
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_academic_cohorts"
down_revision = "0007_public_limits_and_membership"
branch_labels = None
depends_on = None

SUH_ID = "192b6a88-03c6-515a-afcc-0cb6055b59fd"
DEPARTMENT_ID = "suh-dept-cse"
BRANCHES = (
    ("suh-branch-cse", "Computer Science Engineering"),
    ("suh-branch-aiml", "CSE – Artificial Intelligence and Machine Learning"),
    ("suh-branch-ds", "CSE – Data Science"),
    ("suh-branch-cyber", "CSE – Cyber Security"),
    ("suh-branch-sap", "CSE – SAP Integrated Program"),
)


def upgrade():
    op.create_table(
        "departments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("college_id", sa.String(), sa.ForeignKey("colleges.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("college_id", "code", name="uq_departments_college_code"),
    )
    with op.batch_alter_table("courses") as batch:
        batch.add_column(sa.Column("department_id", sa.String(), nullable=True))
        batch.create_foreign_key(
            "fk_courses_department_id_departments", "departments", ["department_id"], ["id"]
        )
    with op.batch_alter_table("profiles") as batch:
        batch.add_column(sa.Column("department_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("year_of_study", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_profiles_department_id_departments", "departments", ["department_id"], ["id"]
        )
        batch.create_check_constraint(
            "ck_profiles_year_of_study", "year_of_study IS NULL OR year_of_study BETWEEN 1 AND 4"
        )

    op.create_table(
        "academic_subjects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("course_id", sa.String(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "course_id", "semester", "code", name="uq_academic_subject_scope_code"
        ),
        sa.CheckConstraint("semester BETWEEN 1 AND 8", name="ck_academic_subject_semester"),
    )
    op.create_table(
        "academic_resources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("subject_id", sa.String(), sa.ForeignKey("academic_subjects.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("source_label", sa.String(200), nullable=True),
        sa.Column("unit_number", sa.Integer(), nullable=True),
        sa.Column("unit_title", sa.String(200), nullable=True),
        sa.Column("academic_session", sa.String(20), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "unit_number IS NULL OR unit_number >= 1",
            name="ck_academic_resources_unit_positive",
        ),
    )
    op.create_index(
        "ix_academic_resources_subject_published",
        "academic_resources", ["subject_id", "is_published"]
    )

    bind = op.get_bind()
    department = sa.table(
        "departments",
        sa.column("id", sa.String()),
        sa.column("college_id", sa.String()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
    )
    course = sa.table(
        "courses",
        sa.column("id", sa.String()),
        sa.column("college_id", sa.String()),
        sa.column("department_id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("degree", sa.String()),
    )
    college_exists = bind.execute(
        sa.text("SELECT id FROM colleges WHERE id = :id"), {"id": SUH_ID}
    ).scalar()
    if college_exists:
        if bind.execute(
            sa.text("SELECT id FROM departments WHERE id = :id"), {"id": DEPARTMENT_ID}
        ).scalar() is None:
            bind.execute(department.insert().values(
                id=DEPARTMENT_ID,
                college_id=SUH_ID,
                code="CSE",
                name="Computer Science and Engineering",
            ))
        for branch_id, branch_name in BRANCHES:
            existing = bind.execute(
                sa.text(
                    "SELECT id FROM courses WHERE college_id = :college AND "
                    "lower(name) = lower(:name) LIMIT 1"
                ), {"college": SUH_ID, "name": branch_name}
            ).scalar()
            if existing:
                bind.execute(
                    course.update().where(
                        sa.and_(course.c.id == existing, course.c.department_id.is_(None))
                    ).values(department_id=DEPARTMENT_ID)
                )
            else:
                bind.execute(course.insert().values(
                    id=branch_id,
                    college_id=SUH_ID,
                    department_id=DEPARTMENT_ID,
                    name=branch_name,
                    degree="B.Tech",
                ))


def downgrade():
    op.drop_index("ix_academic_resources_subject_published", table_name="academic_resources")
    op.drop_table("academic_resources")
    op.drop_table("academic_subjects")

    # Remove only catalog branches created by this migration and not in use.
    # Never delete a course referenced by a student profile or subject.
    bind = op.get_bind()
    for branch_id, branch_name in BRANCHES:
        used_by_profile = bind.execute(
            sa.text("SELECT 1 FROM profiles WHERE course_id=:id LIMIT 1"), {"id": branch_id}
        ).first()
        used_by_subject = bind.execute(
            sa.text("SELECT 1 FROM subjects WHERE course_id=:id LIMIT 1"), {"id": branch_id}
        ).first()
        if used_by_profile or used_by_subject:
            continue
        bind.execute(
            sa.text(
                "DELETE FROM courses WHERE id=:id AND college_id=:college AND name=:name"
            ),
            {"id": branch_id, "college": SUH_ID, "name": branch_name},
        )
    with op.batch_alter_table("profiles") as batch:
        batch.drop_constraint("ck_profiles_year_of_study", type_="check")
        batch.drop_constraint("fk_profiles_department_id_departments", type_="foreignkey")
        batch.drop_column("year_of_study")
        batch.drop_column("department_id")
    with op.batch_alter_table("courses") as batch:
        batch.drop_constraint("fk_courses_department_id_departments", type_="foreignkey")
        batch.drop_column("department_id")
    op.drop_table("departments")
