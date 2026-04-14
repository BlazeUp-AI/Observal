"""Add api_keys table for multi-key management with expiration and rotation.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("prefix", sa.String(10), nullable=False),
        sa.Column(
            "environment",
            sa.Enum("live", "test", "dev", name="apikeyenvironment"),
            nullable=False,
            server_default="live",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_ip", sa.String(45), nullable=True),
        sa.Column("scope", sa.JSON, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "name", name="uq_api_keys_user_name"),
        sa.CheckConstraint("length(name) >= 1 AND length(name) <= 100", name="ck_api_keys_name_length"),
    )

    # Create indexes
    op.create_index("idx_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index(
        "idx_api_keys_active_lookup",
        "api_keys",
        ["key_hash", "user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index("idx_api_keys_user_environment", "api_keys", ["user_id", "environment"])

    # Migrate existing api_key_hash from users table to api_keys
    # Note: This SQL will be executed during migration
    op.execute(
        """
        INSERT INTO api_keys (id, user_id, name, key_hash, prefix, environment, created_at, expires_at)
        SELECT
            gen_random_uuid(),
            id,
            'Key created ' || to_char(created_at, 'YYYY-MM-DD'),
            api_key_hash,
            'obs_live_',  -- Legacy keys don't have real prefix, use placeholder
            'live',
            created_at,
            NULL  -- No expiration for legacy keys
        FROM users
        WHERE api_key_hash IS NOT NULL AND api_key_hash != '';
        """
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("idx_api_keys_user_environment", table_name="api_keys")
    op.drop_index("idx_api_keys_active_lookup", table_name="api_keys")
    op.drop_index("idx_api_keys_key_hash", table_name="api_keys")

    # Drop table
    op.drop_table("api_keys")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS apikeyenvironment")
