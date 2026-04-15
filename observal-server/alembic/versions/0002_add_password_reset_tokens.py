"""Add password_reset_tokens table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-14
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'password_reset_tokens'
            ) THEN
                CREATE TABLE password_reset_tokens (
                    id UUID PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    token_hash VARCHAR(64) NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE INDEX ix_password_reset_tokens_email ON password_reset_tokens (email);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_reset_tokens")
