"""Initial schema baseline

This revision exists solely as the alembic baseline marker. The actual schema
is created by Base.metadata.create_all in the application lifespan (main.py)
and in the Docker entrypoint before migrations run.

All 28 prior incremental migrations (0001-0028) have been squashed into this
single no-op revision. The hosted database already has every table and column,
so there is nothing for a migration to do — this file just marks "you are at
head."

Future migrations should set:
    down_revision = "0001"

Revision ID: 0001
Revises: None
Create Date: 2026-05-05
"""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: schema is managed via Base.metadata.create_all on fresh installs.
    # This revision exists only to provide an alembic version anchor.
    pass


def downgrade() -> None:
    # No-op: there is no prior revision to downgrade to.
    pass
