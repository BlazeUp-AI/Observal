"""Drop password_reset_tokens table.

The self-service reset-code flow has been deprecated. Admins reset
passwords directly via the admin API.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-14
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_reset_tokens")


def downgrade() -> None:
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
