"""Normalize email to lowercase and add case-insensitive unique index.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-15
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the case-sensitive constraint first to avoid conflicts during lowercasing
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'users_email_key' AND table_name = 'users'
            ) THEN
                ALTER TABLE users DROP CONSTRAINT users_email_key;
            END IF;
        END
        $$;
    """)
    op.execute("UPDATE users SET email = LOWER(TRIM(email))")
    # Remove duplicate emails, keeping the oldest account
    op.execute("""
        DELETE FROM users a USING users b
        WHERE a.created_at > b.created_at
          AND LOWER(a.email) = LOWER(b.email)
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'ix_users_email_lower'
            ) THEN
                CREATE UNIQUE INDEX ix_users_email_lower ON users (LOWER(email));
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_email_lower")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'users_email_key' AND table_name = 'users'
            ) THEN
                ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);
            END IF;
        END
        $$;
    """)
