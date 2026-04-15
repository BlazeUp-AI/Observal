"""Add api_keys table for multi-key management with expiration and rotation.

NOTE: api_keys were fully removed in 0006. This migration is kept for
chain continuity but is a no-op — it only creates the table if it
already exists (i.e. on databases that predate the removal).

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-14
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: api_keys table was removed in 0006.
    pass


def downgrade() -> None:
    pass
