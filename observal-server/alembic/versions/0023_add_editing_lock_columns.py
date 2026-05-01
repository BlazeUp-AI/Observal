"""Add editing lock columns to all version tables.

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-01
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, Sequence[str], None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VERSION_TABLES = [
    "mcp_versions",
    "skill_versions",
    "hook_versions",
    "prompt_versions",
    "sandbox_versions",
    "agent_versions",
]


def upgrade() -> None:
    for table in VERSION_TABLES:
        op.add_column(table, sa.Column("is_editing", sa.Boolean(), server_default=sa.text("false"), nullable=False))
        op.add_column(table, sa.Column("editing_since", sa.DateTime(timezone=True), nullable=True))
        op.add_column(
            table,
            sa.Column("editing_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )


def downgrade() -> None:
    for table in VERSION_TABLES:
        op.drop_column(table, "editing_by")
        op.drop_column(table, "editing_since")
        op.drop_column(table, "is_editing")
