"""Add alert_history table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-14
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'alert_history'
            ) THEN
                CREATE TABLE alert_history (
                    id UUID PRIMARY KEY,
                    alert_rule_id UUID NOT NULL REFERENCES alert_rules(id),
                    metric_value DOUBLE PRECISION NOT NULL,
                    threshold DOUBLE PRECISION NOT NULL,
                    condition VARCHAR(10) NOT NULL,
                    fired_at TIMESTAMPTZ NOT NULL,
                    delivery_status VARCHAR(20) DEFAULT 'pending',
                    response_code INTEGER,
                    error VARCHAR(1024),
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            END IF;
        END
        $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'ix_alert_history_alert_rule_id'
            ) THEN
                CREATE INDEX ix_alert_history_alert_rule_id ON alert_history (alert_rule_id);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'alert_history'
            ) THEN
                DROP TABLE alert_history;
            END IF;
        END
        $$;
    """)
