"""Add docker_image column to mcp_listings.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-15
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'docker_image'
            ) THEN
                ALTER TABLE mcp_listings ADD COLUMN docker_image VARCHAR(500);
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
                WHERE table_name = 'mcp_listings' AND column_name = 'docker_image'
            ) THEN
                ALTER TABLE mcp_listings DROP COLUMN docker_image;
            END IF;
        END
        $$;
    """)
