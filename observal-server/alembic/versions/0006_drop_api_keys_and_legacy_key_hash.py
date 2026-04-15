"""Drop api_keys table and users.api_key_hash column.

JWT is now the sole auth mechanism — API keys are no longer used.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-15
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop indexes and table only if they exist (may not on fresh DBs)
    op.execute("DROP INDEX IF EXISTS idx_api_keys_user_environment")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_active_lookup")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_key_hash")
    op.execute("DROP TABLE IF EXISTS api_keys")
    op.execute("DROP TYPE IF EXISTS apikeyenvironment")

    # Drop legacy column if it exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'api_key_hash'
            ) THEN
                ALTER TABLE users DROP COLUMN api_key_hash;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'api_key_hash'
            ) THEN
                ALTER TABLE users ADD COLUMN api_key_hash VARCHAR(64);
            END IF;
        END
        $$;
    """)
