"""Add gaming_flags JSONB column to agent_versions

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-04 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0028"
down_revision: Union[str, Sequence[str], None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_versions",
        sa.Column("gaming_flags", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_versions", "gaming_flags")
