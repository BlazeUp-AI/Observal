"""Add trace_privacy column to organizations.

When enabled, all roles below super-admin can only see their own
traces.  Super-admins always retain full visibility.

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-22
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'organizations' AND column_name = 'trace_privacy'
            ) THEN
                ALTER TABLE organizations ADD COLUMN trace_privacy BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'organizations' AND column_name = 'trace_privacy'
            ) THEN
                ALTER TABLE organizations DROP COLUMN trace_privacy;
            END IF;
        END
        $$;
    """)
