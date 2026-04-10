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
