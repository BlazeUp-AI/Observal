"""Add command, args, url, headers, auto_approve columns to mcp_listings.

Also makes git_url nullable (for direct config submissions without a repo).

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-18
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'command'
            ) THEN
                ALTER TABLE mcp_listings ADD COLUMN command VARCHAR(500);
            END IF;
        END
        $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'args'
            ) THEN
                ALTER TABLE mcp_listings ADD COLUMN args JSON;
            END IF;
        END
        $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'url'
            ) THEN
                ALTER TABLE mcp_listings ADD COLUMN url VARCHAR(1000);
            END IF;
        END
        $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'headers'
            ) THEN
                ALTER TABLE mcp_listings ADD COLUMN headers JSON;
            END IF;
        END
        $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'auto_approve'
            ) THEN
                ALTER TABLE mcp_listings ADD COLUMN auto_approve JSON;
            END IF;
        END
        $$;
    """)

    # Make git_url nullable for direct config submissions
    op.execute("""
        DO $$
        BEGIN
            ALTER TABLE mcp_listings ALTER COLUMN git_url DROP NOT NULL;
        EXCEPTION
            WHEN others THEN NULL;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'command'
            ) THEN
                ALTER TABLE mcp_listings DROP COLUMN command;
            END IF;
        END
        $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'args'
            ) THEN
                ALTER TABLE mcp_listings DROP COLUMN args;
            END IF;
        END
        $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'url'
            ) THEN
                ALTER TABLE mcp_listings DROP COLUMN url;
            END IF;
        END
        $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'headers'
            ) THEN
                ALTER TABLE mcp_listings DROP COLUMN headers;
            END IF;
        END
        $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'mcp_listings' AND column_name = 'auto_approve'
            ) THEN
                ALTER TABLE mcp_listings DROP COLUMN auto_approve;
            END IF;
        END
        $$;
    """)

    # Restore NOT NULL on git_url (may fail if NULLs exist)
    op.execute("""
        DO $$
        BEGIN
            ALTER TABLE mcp_listings ALTER COLUMN git_url SET NOT NULL;
        EXCEPTION
            WHEN others THEN NULL;
        END
        $$;
    """)
