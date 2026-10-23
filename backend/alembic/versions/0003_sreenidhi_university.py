"""Add Sreenidhi University to the college catalog.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SREENIDHI_UNIVERSITY_ID = "192b6a88-03c6-515a-afcc-0cb6055b59fd"
SREENIDHI_UNIVERSITY_NAME = "Sreenidhi University"


def upgrade():
    colleges = sa.table(
        "colleges",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("city", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    connection = op.get_bind()
    existing = connection.execute(
        sa.select(colleges.c.id)
        .where(
            sa.or_(
                colleges.c.id == SREENIDHI_UNIVERSITY_ID,
                sa.func.lower(sa.func.trim(colleges.c.name)) == SREENIDHI_UNIVERSITY_NAME.lower(),
            )
        )
        .limit(1)
    ).first()
    if existing is None:
        connection.execute(
            colleges.insert().values(
                id=SREENIDHI_UNIVERSITY_ID,
                name=SREENIDHI_UNIVERSITY_NAME,
                city="Hyderabad",
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
        )


def downgrade():
    colleges = sa.table(
        "colleges",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
    )
    op.get_bind().execute(
        colleges.delete().where(
            sa.and_(
                colleges.c.id == SREENIDHI_UNIVERSITY_ID,
                colleges.c.name == SREENIDHI_UNIVERSITY_NAME,
            )
        )
    )
