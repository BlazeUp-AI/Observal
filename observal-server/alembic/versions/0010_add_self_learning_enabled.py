# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Add self_learning_enabled to agents table.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("self_learning_enabled", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("agents", "self_learning_enabled")
