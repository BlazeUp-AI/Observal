"""Add 'draft' value to listing_status enum.

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-19
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'draft'
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'listingstatus')
            ) THEN
                ALTER TYPE listingstatus ADD VALUE 'draft' BEFORE 'pending';
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    pass
