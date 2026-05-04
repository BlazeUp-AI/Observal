"""add agent team access

Revision ID: e8e63ca6d74e
Revises: 0018
Create Date: 2026-04-25 19:29:53.469407

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8e63ca6d74e"
down_revision: Union[str, Sequence[str], None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agent_team_access",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("group_name", sa.String(length=255), nullable=False),
        sa.Column("permission", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "agents",
        sa.Column(
            "visibility", sa.Enum("public", "private", name="agentvisibility"), nullable=False, server_default="private"
        ),
    )
    op.drop_column("agents", "is_private")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "agents", sa.Column("is_private", sa.BOOLEAN(), autoincrement=False, nullable=False, server_default="true")
    )
    op.drop_column("agents", "visibility")
    op.drop_table("agent_team_access")
