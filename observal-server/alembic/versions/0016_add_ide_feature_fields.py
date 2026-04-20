"""Add required_ide_features and inferred_supported_ides to agents.

Auto-inferred from agent components so the registry knows which IDEs
are compatible with a given agent.

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-21
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'agents' AND column_name = 'required_ide_features'
            ) THEN
                ALTER TABLE agents ADD COLUMN required_ide_features JSONB DEFAULT '[]'::jsonb;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'agents' AND column_name = 'inferred_supported_ides'
            ) THEN
                ALTER TABLE agents ADD COLUMN inferred_supported_ides JSONB DEFAULT '[]'::jsonb;
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
                WHERE table_name = 'agents' AND column_name = 'required_ide_features'
            ) THEN
                ALTER TABLE agents DROP COLUMN required_ide_features;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'agents' AND column_name = 'inferred_supported_ides'
            ) THEN
                ALTER TABLE agents DROP COLUMN inferred_supported_ides;
            END IF;
        END
        $$;
    """)
