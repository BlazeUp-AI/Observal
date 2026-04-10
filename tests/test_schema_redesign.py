"""Tests for the agent-centric schema redesign."""

import uuid
from datetime import UTC, datetime

import pytest


class TestOrganizationModel:
    def test_organization_tablename(self):
        from models.organization import Organization
        assert Organization.__tablename__ == "organizations"

    def test_organization_has_required_columns(self):
        from models.organization import Organization
        cols = {c.name for c in Organization.__table__.columns}
        assert "id" in cols
        assert "name" in cols
        assert "slug" in cols
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_organization_slug_is_unique(self):
        from models.organization import Organization
        slug_col = Organization.__table__.c.slug
        assert slug_col.unique or any(
            uc for uc in Organization.__table__.constraints
            if hasattr(uc, "columns") and "slug" in [c.name for c in uc.columns]
        )


class TestUserOrgField:
    def test_user_has_org_id(self):
        from models.user import User
        cols = {c.name for c in User.__table__.columns}
        assert "org_id" in cols

    def test_user_org_id_is_nullable(self):
        from models.user import User
        org_col = User.__table__.c.org_id
        assert org_col.nullable is True


class TestComponentSourceModel:
    def test_component_source_tablename(self):
        from models.component_source import ComponentSource
        assert ComponentSource.__tablename__ == "component_sources"

    def test_component_source_has_required_columns(self):
        from models.component_source import ComponentSource
        cols = {c.name for c in ComponentSource.__table__.columns}
        required = {"id", "url", "provider", "component_type", "is_public", "owner_org_id",
                    "auto_sync_interval", "last_synced_at", "sync_status", "sync_error",
                    "created_at", "updated_at"}
        assert required.issubset(cols)

    def test_component_source_url_type_unique(self):
        from models.component_source import ComponentSource
        table = ComponentSource.__table__
        unique_constraints = [
            uc for uc in table.constraints
            if hasattr(uc, "columns") and len(uc.columns) == 2
        ]
        col_sets = [frozenset(c.name for c in uc.columns) for uc in unique_constraints]
        assert frozenset({"url", "component_type"}) in col_sets


class TestComponentTableUpdates:
    """All component tables must have: is_private, owner_org_id, download_count, unique_agents."""

    @pytest.mark.parametrize("model_path,model_name", [
        ("models.mcp", "McpListing"),
        ("models.skill", "SkillListing"),
        ("models.hook", "HookListing"),
        ("models.prompt", "PromptListing"),
        ("models.sandbox", "SandboxListing"),
    ])
    def test_component_has_org_fields(self, model_path, model_name):
        import importlib
        mod = importlib.import_module(model_path)
        cls = getattr(mod, model_name)
        cols = {c.name for c in cls.__table__.columns}
        assert "is_private" in cols, f"{model_name} missing is_private"
        assert "owner_org_id" in cols, f"{model_name} missing owner_org_id"

    @pytest.mark.parametrize("model_path,model_name", [
        ("models.mcp", "McpListing"),
        ("models.skill", "SkillListing"),
        ("models.hook", "HookListing"),
        ("models.prompt", "PromptListing"),
        ("models.sandbox", "SandboxListing"),
    ])
    def test_component_has_download_counts(self, model_path, model_name):
        import importlib
        mod = importlib.import_module(model_path)
        cls = getattr(mod, model_name)
        cols = {c.name for c in cls.__table__.columns}
        assert "download_count" in cols, f"{model_name} missing download_count"
        assert "unique_agents" in cols, f"{model_name} missing unique_agents"

    @pytest.mark.parametrize("model_path,model_name", [
        ("models.mcp", "McpListing"),
        ("models.skill", "SkillListing"),
        ("models.hook", "HookListing"),
        ("models.prompt", "PromptListing"),
        ("models.sandbox", "SandboxListing"),
    ])
    def test_component_has_git_url(self, model_path, model_name):
        import importlib
        mod = importlib.import_module(model_path)
        cls = getattr(mod, model_name)
        cols = {c.name for c in cls.__table__.columns}
        assert "git_url" in cols, f"{model_name} missing git_url"

    @pytest.mark.parametrize("model_path,model_name", [
        ("models.mcp", "McpListing"),
        ("models.skill", "SkillListing"),
        ("models.hook", "HookListing"),
        ("models.prompt", "PromptListing"),
        ("models.sandbox", "SandboxListing"),
    ])
    def test_component_has_git_ref(self, model_path, model_name):
        import importlib
        mod = importlib.import_module(model_path)
        cls = getattr(mod, model_name)
        cols = {c.name for c in cls.__table__.columns}
        assert "git_ref" in cols, f"{model_name} missing git_ref"

    def test_mcp_has_fastmcp_validated(self):
        from models.mcp import McpListing
        cols = {c.name for c in McpListing.__table__.columns}
        assert "fastmcp_validated" in cols

    def test_skill_link_table_removed(self):
        """AgentSkillLink should no longer exist — replaced by AgentComponent."""
        from models import skill
        assert not hasattr(skill, "AgentSkillLink")

    def test_hook_link_table_removed(self):
        """AgentHookLink should no longer exist — replaced by AgentComponent."""
        from models import hook
        assert not hasattr(hook, "AgentHookLink")


class TestAgentModelUpdate:
    def test_agent_has_org_fields(self):
        from models.agent import Agent
        cols = {c.name for c in Agent.__table__.columns}
        assert "is_private" in cols
        assert "owner_org_id" in cols

    def test_agent_has_git_url(self):
        from models.agent import Agent
        cols = {c.name for c in Agent.__table__.columns}
        assert "git_url" in cols

    def test_agent_has_download_metrics(self):
        from models.agent import Agent
        cols = {c.name for c in Agent.__table__.columns}
        assert "download_count" in cols
        assert "unique_users" in cols

    def test_agent_git_url_is_nullable(self):
        from models.agent import Agent
        git_col = Agent.__table__.c.git_url
        assert git_col.nullable is True

    def test_agent_mcp_link_removed(self):
        """AgentMcpLink should no longer exist — replaced by AgentComponent."""
        from models import agent
        assert not hasattr(agent, "AgentMcpLink")


class TestAgentComponentModel:
    def test_agent_component_tablename(self):
        from models.agent_component import AgentComponent
        assert AgentComponent.__tablename__ == "agent_components"

    def test_agent_component_has_required_columns(self):
        from models.agent_component import AgentComponent
        cols = {c.name for c in AgentComponent.__table__.columns}
        required = {"id", "agent_id", "component_type", "component_id",
                    "version_ref", "order_index", "config_override", "created_at"}
        assert required.issubset(cols)

    def test_agent_component_has_unique_constraint(self):
        from models.agent_component import AgentComponent
        table = AgentComponent.__table__
        unique_constraints = [
            uc for uc in table.constraints
            if hasattr(uc, "columns") and len(uc.columns) == 3
        ]
        col_sets = [frozenset(c.name for c in uc.columns) for uc in unique_constraints]
        assert frozenset({"agent_id", "component_type", "component_id"}) in col_sets

    def test_agent_component_no_fk_on_component_id(self):
        """component_id should NOT have a FK constraint (polymorphic, future flexibility)."""
        from models.agent_component import AgentComponent
        col = AgentComponent.__table__.c.component_id
        fks = col.foreign_keys
        assert len(fks) == 0, "component_id should have no FK constraints"
