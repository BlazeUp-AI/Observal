"""make insight_reports.triggered_by nullable for cron-triggered reports

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-04 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0026"
down_revision: Union[str, Sequence[str], None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make triggered_by nullable to support cron-triggered reports."""
    op.alter_column("insight_reports", "triggered_by", nullable=True)


def downgrade() -> None:
    """Revert triggered_by to non-nullable."""
    op.alter_column("insight_reports", "triggered_by", nullable=False)
