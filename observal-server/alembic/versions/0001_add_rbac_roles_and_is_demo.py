"""Add super_admin and reviewer roles, rename developer to reviewer, add is_demo column.

Revision ID: 0001
Revises:
Create Date: 2026-04-13
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'reviewer'")
    # New enum values must be committed before they can be used in DML
    op.execute("COMMIT")
    # Only rename developer→reviewer if the enum still has the old value
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'developer'
                  AND enumtypid = 'userrole'::regtype
            ) THEN
                UPDATE users SET role = 'reviewer' WHERE role = 'developer';
            END IF;
        END
        $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'is_demo'
            ) THEN
                ALTER TABLE users ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT false;
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
                WHERE table_name = 'users' AND column_name = 'is_demo'
            ) THEN
                ALTER TABLE users DROP COLUMN is_demo;
            END IF;
        END
        $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'developer'
                  AND enumtypid = 'userrole'::regtype
            ) THEN
                UPDATE users SET role = 'developer' WHERE role = 'reviewer';
            END IF;
        END
        $$;
    """)
