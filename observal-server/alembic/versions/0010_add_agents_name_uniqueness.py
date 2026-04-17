"""Add unique constraint on agents (name, created_by).

Same user cannot create two agents with the same name; different users can.

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-17
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deduplicate any existing duplicates first: keep the most recent row,
    # rename older duplicates by appending a suffix so the index can be created.
    op.execute("""
        DO $$
        DECLARE
            dup_row RECORD;
            inner_row RECORD;
            counter INT;
        BEGIN
            FOR dup_row IN
                SELECT name, created_by FROM agents
                GROUP BY name, created_by HAVING COUNT(*) > 1
            LOOP
                counter := 0;
                FOR inner_row IN
                    SELECT id FROM agents
                    WHERE name = dup_row.name AND created_by = dup_row.created_by
                    ORDER BY created_at DESC OFFSET 1
                LOOP
                    counter := counter + 1;
                    UPDATE agents
                    SET name = name || '-dup' || counter
                    WHERE id = inner_row.id;
                END LOOP;
            END LOOP;
        END
        $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_agents_name_created_by'
            ) THEN
                ALTER TABLE agents
                ADD CONSTRAINT uq_agents_name_created_by UNIQUE (name, created_by);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE agents DROP CONSTRAINT IF EXISTS uq_agents_name_created_by;")
