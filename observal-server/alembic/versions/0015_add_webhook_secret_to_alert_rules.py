"""Add webhook_secret column to alert_rules table.

Stores per-rule HMAC signing secrets for outbound webhook verification.
Existing rules get empty string (unsigned delivery, backwards-compatible).

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-20
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'alert_rules' AND column_name = 'webhook_secret'
            ) THEN
                ALTER TABLE alert_rules ADD COLUMN webhook_secret VARCHAR(255) DEFAULT '' NOT NULL;
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
                WHERE table_name = 'alert_rules' AND column_name = 'webhook_secret'
            ) THEN
                ALTER TABLE alert_rules DROP COLUMN webhook_secret;
            END IF;
        END
        $$;
    """)
