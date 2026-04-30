"""add agent version tables and restructure agent to identity-only

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-30 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, Sequence[str], None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reuse the existing agentstatus enum — do not create a new one.
agent_status = postgresql.ENUM(
    "draft", "pending", "approved", "rejected", "archived", name="agentstatus", create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Rename 'active' -> 'approved' on the agentstatus enum
    # ------------------------------------------------------------------
    conn.execute(sa.text("ALTER TYPE agentstatus RENAME VALUE 'active' TO 'approved'"))

    # ------------------------------------------------------------------
    # 2. Create agent_versions table
    # ------------------------------------------------------------------
    op.create_table(
        "agent_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("model_config_json", sa.JSON(), server_default="{}"),
        sa.Column("external_mcps", sa.JSON(), server_default="[]"),
        sa.Column("supported_ides", sa.JSON(), server_default="[]"),
        sa.Column("required_ide_features", sa.JSON(), server_default="[]"),
        sa.Column("inferred_supported_ides", sa.JSON(), server_default="[]"),
        sa.Column("yaml_snapshot", sa.Text(), nullable=True),
        sa.Column("ide_configs", sa.JSON(), nullable=True),
        sa.Column("lock_snapshot", sa.Text(), nullable=True),
        sa.Column("status", agent_status, nullable=True, server_default="pending"),
        sa.Column("is_prerelease", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("promoted_from", sa.UUID(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("released_by", sa.UUID(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
    )
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])
    op.create_index("ix_agent_versions_status", "agent_versions", ["status"])

    # ------------------------------------------------------------------
    # 3. Data migration: seed one agent_version row per existing agent
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("""
        INSERT INTO agent_versions (
            id, agent_id, version, description, prompt,
            model_name, model_config_json, external_mcps,
            supported_ides, required_ide_features, inferred_supported_ides,
            status, rejection_reason, download_count,
            released_by, released_at, created_at
        )
        SELECT
            gen_random_uuid(),
            id,
            COALESCE(version, '1.0.0'),
            description,
            prompt,
            model_name,
            model_config_json,
            external_mcps,
            supported_ides,
            required_ide_features,
            inferred_supported_ides,
            status,
            rejection_reason,
            download_count,
            created_by,
            created_at,
            now()
        FROM agents
    """)
    )

    # ------------------------------------------------------------------
    # 4. Add latest_version_id + co_maintainers to agents
    # ------------------------------------------------------------------
    op.add_column("agents", sa.Column("latest_version_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_agents_latest_version_id",
        "agents",
        "agent_versions",
        ["latest_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("agents", sa.Column("co_maintainers", sa.JSON(), server_default="[]", nullable=False))

    # Set latest_version_id to the newly created version row for each agent
    conn.execute(
        sa.text("""
        UPDATE agents a
        SET latest_version_id = av.id
        FROM agent_versions av
        WHERE av.agent_id = a.id
    """)
    )

    # ------------------------------------------------------------------
    # 5. Migrate agent_components: agent_id -> agent_version_id
    # ------------------------------------------------------------------
    op.add_column("agent_components", sa.Column("agent_version_id", sa.UUID(), nullable=True))
    op.add_column(
        "agent_components",
        sa.Column("component_name", sa.String(255), server_default="", nullable=False),
    )

    conn.execute(
        sa.text("""
        UPDATE agent_components ac
        SET agent_version_id = (
            SELECT av.id
            FROM agent_versions av
            WHERE av.agent_id = ac.agent_id
            LIMIT 1
        )
    """)
    )

    # Rename version_ref -> resolved_version and change type to varchar(50)
    op.alter_column(
        "agent_components",
        "version_ref",
        new_column_name="resolved_version",
        type_=sa.String(50),
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    # Make agent_version_id NOT NULL
    op.alter_column("agent_components", "agent_version_id", nullable=False)

    # Drop old constraints before dropping the column they reference
    op.drop_constraint("uq_agent_components_agent_type_component", "agent_components", type_="unique")
    op.drop_constraint("agent_components_agent_id_fkey", "agent_components", type_="foreignkey")
    op.drop_column("agent_components", "agent_id")

    # Add new unique constraint
    op.create_unique_constraint(
        "uq_agent_components_version_type_component",
        "agent_components",
        ["agent_version_id", "component_type", "component_id"],
    )

    # Add FK from agent_version_id to agent_versions.id
    op.create_foreign_key(
        "fk_agent_components_agent_version_id",
        "agent_components",
        "agent_versions",
        ["agent_version_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ------------------------------------------------------------------
    # 6. Migrate agent_goal_templates: agent_id -> agent_version_id
    # ------------------------------------------------------------------
    op.add_column("agent_goal_templates", sa.Column("agent_version_id", sa.UUID(), nullable=True))

    conn.execute(
        sa.text("""
        UPDATE agent_goal_templates agt
        SET agent_version_id = (
            SELECT av.id
            FROM agent_versions av
            WHERE av.agent_id = agt.agent_id
            LIMIT 1
        )
    """)
    )

    op.alter_column("agent_goal_templates", "agent_version_id", nullable=False)
    op.drop_constraint("agent_goal_templates_agent_id_fkey", "agent_goal_templates", type_="foreignkey")
    op.drop_column("agent_goal_templates", "agent_id")

    op.create_foreign_key(
        "fk_agent_goal_templates_agent_version_id",
        "agent_goal_templates",
        "agent_versions",
        ["agent_version_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_agent_goal_templates_agent_version_id",
        "agent_goal_templates",
        ["agent_version_id"],
    )

    # ------------------------------------------------------------------
    # 7. Drop version-specific columns from agents
    # ------------------------------------------------------------------
    op.drop_column("agents", "version")
    op.drop_column("agents", "description")
    op.drop_column("agents", "git_url")
    op.drop_column("agents", "prompt")
    op.drop_column("agents", "model_name")
    op.drop_column("agents", "model_config_json")
    op.drop_column("agents", "external_mcps")
    op.drop_column("agents", "supported_ides")
    op.drop_column("agents", "required_ide_features")
    op.drop_column("agents", "inferred_supported_ides")
    op.drop_column("agents", "status")
    op.drop_column("agents", "rejection_reason")
    op.drop_column("agents", "download_count")
    op.drop_column("agents", "unique_users")


def downgrade() -> None:
    """Downgrade schema."""
    raise NotImplementedError("Clean-break migration")
