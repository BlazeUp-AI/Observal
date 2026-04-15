"""Add framework column to mcp_listings.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-15
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'framework'
            ) THEN
                ALTER TABLE mcp_listings ADD COLUMN framework VARCHAR(100);
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
                WHERE table_name = 'mcp_listings' AND column_name = 'framework'
            ) THEN
                ALTER TABLE mcp_listings DROP COLUMN framework;
            END IF;
        END
        $$;
    """)
