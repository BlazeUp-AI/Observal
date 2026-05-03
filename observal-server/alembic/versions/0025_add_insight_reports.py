"""add insight_reports table for Agent Insights V1

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-04 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, Sequence[str], None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create insight_reports table."""
    op.create_table(
        "insight_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("triggered_by", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="insightreportstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("narrative", sa.JSON(), nullable=True),
        sa.Column("sessions_analyzed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_model_used", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insight_reports_agent_id", "insight_reports", ["agent_id"])
    op.create_index("ix_insight_reports_status", "insight_reports", ["status"])


def downgrade() -> None:
    """Drop insight_reports table."""
    op.drop_index("ix_insight_reports_status", table_name="insight_reports")
    op.drop_index("ix_insight_reports_agent_id", table_name="insight_reports")
    op.drop_table("insight_reports")
    op.execute("DROP TYPE IF EXISTS insightreportstatus")
