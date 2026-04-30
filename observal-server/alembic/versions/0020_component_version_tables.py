"""add component version tables

Revision ID: 0020
Revises: e8e63ca6d74e
Create Date: 2026-04-30 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, Sequence[str], None] = "e8e63ca6d74e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reuse the existing listingstatus enum — do not create a new one.
listing_status = postgresql.ENUM(
    "draft", "pending", "approved", "rejected", "archived", name="listingstatus", create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    # ------------------------------------------------------------------
    # mcp_versions
    # ------------------------------------------------------------------
    op.create_table(
        "mcp_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("supported_ides", sa.JSON(), server_default="[]", nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("resolved_sha", sa.String(40), nullable=True),
        sa.Column("status", listing_status, nullable=True, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("released_by", sa.UUID(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        # mcp-specific
        sa.Column("transport", sa.String(20), nullable=True),
        sa.Column("framework", sa.String(100), nullable=True),
        sa.Column("docker_image", sa.String(500), nullable=True),
        sa.Column("command", sa.String(500), nullable=True),
        sa.Column("args", sa.JSON(), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("auto_approve", sa.JSON(), nullable=True),
        sa.Column("mcp_validated", sa.Boolean(), server_default="false", nullable=True),
        sa.Column("tools_schema", sa.JSON(), nullable=True),
        sa.Column("environment_variables", sa.JSON(), nullable=True),
        sa.Column("setup_instructions", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["listing_id"], ["mcp_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "version"),
    )
    op.create_index("ix_mcp_versions_listing_id", "mcp_versions", ["listing_id"])
    op.create_index("ix_mcp_versions_status", "mcp_versions", ["status"])

    # ------------------------------------------------------------------
    # skill_versions
    # ------------------------------------------------------------------
    op.create_table(
        "skill_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("supported_ides", sa.JSON(), server_default="[]", nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("resolved_sha", sa.String(40), nullable=True),
        sa.Column("status", listing_status, nullable=True, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("released_by", sa.UUID(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        # skill-specific
        sa.Column("skill_path", sa.String(500), server_default="/", nullable=True),
        sa.Column("target_agents", sa.JSON(), server_default="[]", nullable=True),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("triggers", sa.JSON(), nullable=True),
        sa.Column("slash_command", sa.String(100), nullable=True),
        sa.Column("has_scripts", sa.Boolean(), server_default="false", nullable=True),
        sa.Column("has_templates", sa.Boolean(), server_default="false", nullable=True),
        sa.Column("is_power", sa.Boolean(), server_default="false", nullable=True),
        sa.Column("power_md", sa.Text(), nullable=True),
        sa.Column("mcp_server_config", sa.JSON(), nullable=True),
        sa.Column("activation_keywords", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["listing_id"], ["skill_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "version"),
    )
    op.create_index("ix_skill_versions_listing_id", "skill_versions", ["listing_id"])
    op.create_index("ix_skill_versions_status", "skill_versions", ["status"])

    # ------------------------------------------------------------------
    # hook_versions
    # ------------------------------------------------------------------
    op.create_table(
        "hook_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("supported_ides", sa.JSON(), server_default="[]", nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("resolved_sha", sa.String(40), nullable=True),
        sa.Column("status", listing_status, nullable=True, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("released_by", sa.UUID(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        # hook-specific
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("execution_mode", sa.String(10), server_default="async", nullable=True),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=True),
        sa.Column("handler_type", sa.String(20), nullable=False),
        sa.Column("handler_config", sa.JSON(), server_default="{}", nullable=True),
        sa.Column("input_schema", sa.JSON(), nullable=True),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column("scope", sa.String(20), server_default="agent", nullable=True),
        sa.Column("tool_filter", sa.JSON(), nullable=True),
        sa.Column("file_pattern", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["listing_id"], ["hook_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "version"),
    )
    op.create_index("ix_hook_versions_listing_id", "hook_versions", ["listing_id"])
    op.create_index("ix_hook_versions_status", "hook_versions", ["status"])

    # ------------------------------------------------------------------
    # prompt_versions
    # ------------------------------------------------------------------
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("supported_ides", sa.JSON(), server_default="[]", nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("resolved_sha", sa.String(40), nullable=True),
        sa.Column("status", listing_status, nullable=True, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("released_by", sa.UUID(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        # prompt-specific
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), server_default="[]", nullable=True),
        sa.Column("model_hints", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), server_default="[]", nullable=True),
        sa.ForeignKeyConstraint(["listing_id"], ["prompt_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "version"),
    )
    op.create_index("ix_prompt_versions_listing_id", "prompt_versions", ["listing_id"])
    op.create_index("ix_prompt_versions_status", "prompt_versions", ["status"])

    # ------------------------------------------------------------------
    # sandbox_versions
    # ------------------------------------------------------------------
    op.create_table(
        "sandbox_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("supported_ides", sa.JSON(), server_default="[]", nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("resolved_sha", sa.String(40), nullable=True),
        sa.Column("status", listing_status, nullable=True, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("released_by", sa.UUID(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        # sandbox-specific
        sa.Column("runtime_type", sa.String(20), nullable=False),
        sa.Column("image", sa.String(500), nullable=False),
        sa.Column("dockerfile_url", sa.String(500), nullable=True),
        sa.Column("resource_limits", sa.JSON(), server_default="{}", nullable=True),
        sa.Column("network_policy", sa.String(20), server_default="none", nullable=True),
        sa.Column("allowed_mounts", sa.JSON(), server_default="[]", nullable=True),
        sa.Column("env_vars", sa.JSON(), server_default="{}", nullable=True),
        sa.Column("entrypoint", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["listing_id"], ["sandbox_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "version"),
    )
    op.create_index("ix_sandbox_versions_listing_id", "sandbox_versions", ["listing_id"])
    op.create_index("ix_sandbox_versions_status", "sandbox_versions", ["status"])

    # ------------------------------------------------------------------
    # Add latest_version_id to each listing table
    # ------------------------------------------------------------------
    op.add_column("mcp_listings", sa.Column("latest_version_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_mcp_listings_latest_version_id",
        "mcp_listings",
        "mcp_versions",
        ["latest_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("skill_listings", sa.Column("latest_version_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_skill_listings_latest_version_id",
        "skill_listings",
        "skill_versions",
        ["latest_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("hook_listings", sa.Column("latest_version_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_hook_listings_latest_version_id",
        "hook_listings",
        "hook_versions",
        ["latest_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("prompt_listings", sa.Column("latest_version_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_prompt_listings_latest_version_id",
        "prompt_listings",
        "prompt_versions",
        ["latest_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("sandbox_listings", sa.Column("latest_version_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_sandbox_listings_latest_version_id",
        "sandbox_listings",
        "sandbox_versions",
        ["latest_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # Data migration: seed one version row per existing listing
    # ------------------------------------------------------------------
    conn = op.get_bind()

    # mcp
    conn.execute(
        sa.text("""
        INSERT INTO mcp_versions (
            id, listing_id, version, description, changelog,
            supported_ides, source_url, source_ref,
            status, rejection_reason, download_count,
            released_by, released_at, created_at,
            transport, framework, docker_image, command, args,
            url, headers, auto_approve, mcp_validated,
            tools_schema, environment_variables, setup_instructions
        )
        SELECT
            gen_random_uuid(),
            id,
            COALESCE(version, '1.0.0'),
            description,
            changelog,
            supported_ides,
            git_url,
            git_ref,
            status,
            rejection_reason,
            download_count,
            submitted_by,
            created_at,
            now(),
            transport,
            framework,
            docker_image,
            command,
            args,
            url,
            headers,
            auto_approve,
            mcp_validated,
            tools_schema,
            environment_variables,
            setup_instructions
        FROM mcp_listings
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE mcp_listings l
        SET latest_version_id = v.id
        FROM mcp_versions v
        WHERE v.listing_id = l.id
    """)
    )

    # skill
    conn.execute(
        sa.text("""
        INSERT INTO skill_versions (
            id, listing_id, version, description,
            supported_ides, source_url, source_ref,
            status, rejection_reason, download_count,
            released_by, released_at, created_at,
            skill_path, target_agents, task_type, triggers,
            slash_command, has_scripts, has_templates, is_power,
            power_md, mcp_server_config, activation_keywords
        )
        SELECT
            gen_random_uuid(),
            id,
            COALESCE(version, '1.0.0'),
            description,
            supported_ides,
            git_url,
            git_ref,
            status,
            rejection_reason,
            download_count,
            submitted_by,
            created_at,
            now(),
            skill_path,
            target_agents,
            task_type,
            triggers,
            slash_command,
            has_scripts,
            has_templates,
            is_power,
            power_md,
            mcp_server_config,
            activation_keywords
        FROM skill_listings
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE skill_listings l
        SET latest_version_id = v.id
        FROM skill_versions v
        WHERE v.listing_id = l.id
    """)
    )

    # hook
    conn.execute(
        sa.text("""
        INSERT INTO hook_versions (
            id, listing_id, version, description,
            supported_ides, source_url, source_ref,
            status, rejection_reason, download_count,
            released_by, released_at, created_at,
            event, execution_mode, priority, handler_type,
            handler_config, input_schema, output_schema, scope,
            tool_filter, file_pattern
        )
        SELECT
            gen_random_uuid(),
            id,
            COALESCE(version, '1.0.0'),
            description,
            supported_ides,
            git_url,
            git_ref,
            status,
            rejection_reason,
            download_count,
            submitted_by,
            created_at,
            now(),
            event,
            execution_mode,
            priority,
            handler_type,
            handler_config,
            input_schema,
            output_schema,
            scope,
            tool_filter,
            file_pattern
        FROM hook_listings
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE hook_listings l
        SET latest_version_id = v.id
        FROM hook_versions v
        WHERE v.listing_id = l.id
    """)
    )

    # prompt
    conn.execute(
        sa.text("""
        INSERT INTO prompt_versions (
            id, listing_id, version, description,
            supported_ides, source_url, source_ref,
            status, rejection_reason, download_count,
            released_by, released_at, created_at,
            category, template, variables, model_hints, tags
        )
        SELECT
            gen_random_uuid(),
            id,
            COALESCE(version, '1.0.0'),
            description,
            supported_ides,
            git_url,
            git_ref,
            status,
            rejection_reason,
            download_count,
            submitted_by,
            created_at,
            now(),
            category,
            template,
            variables,
            model_hints,
            tags
        FROM prompt_listings
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE prompt_listings l
        SET latest_version_id = v.id
        FROM prompt_versions v
        WHERE v.listing_id = l.id
    """)
    )

    # sandbox
    conn.execute(
        sa.text("""
        INSERT INTO sandbox_versions (
            id, listing_id, version, description,
            supported_ides, source_url, source_ref,
            status, rejection_reason, download_count,
            released_by, released_at, created_at,
            runtime_type, image, dockerfile_url, resource_limits,
            network_policy, allowed_mounts, env_vars, entrypoint
        )
        SELECT
            gen_random_uuid(),
            id,
            COALESCE(version, '1.0.0'),
            description,
            supported_ides,
            git_url,
            git_ref,
            status,
            rejection_reason,
            download_count,
            submitted_by,
            created_at,
            now(),
            runtime_type,
            image,
            dockerfile_url,
            resource_limits,
            network_policy,
            allowed_mounts,
            env_vars,
            entrypoint
        FROM sandbox_listings
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE sandbox_listings l
        SET latest_version_id = v.id
        FROM sandbox_versions v
        WHERE v.listing_id = l.id
    """)
    )


def downgrade() -> None:
    """Downgrade schema."""
    raise NotImplementedError("Clean-break migration")
