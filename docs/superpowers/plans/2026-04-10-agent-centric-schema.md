# Agent-Centric Schema Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the database schema to make agents the primary entity with components as composable dependencies, adding org support and download tracking.

**Architecture:** Separate SQLAlchemy models per component type (Approach B). Polymorphic `agent_components` junction table links agents to any component type without FK constraints. Deduplicated agent downloads, non-deduplicated component downloads. All components require `git_url` for Git-based versioning. Organization support via `is_private` + `owner_org_id` fields.

**Tech Stack:** SQLAlchemy 2.x async (mapped_column), PostgreSQL 16, pytest with mock DB

**Spec:** `docs/superpowers/specs/2026-04-10-agent-centric-schema-design.md`

---

## File Map

### New Files
- `observal-server/models/organization.py` — Organization model
- `observal-server/models/component_source.py` — ComponentSource model (Git mirror origins)
- `observal-server/models/agent_component.py` — AgentComponent polymorphic junction table
- `observal-server/models/download.py` — AgentDownload (deduplicated) + ComponentDownload (not deduplicated)
- `observal-server/models/exporter_config.py` — ExporterConfig model
- `tests/test_schema_redesign.py` — All tests for the schema redesign

### Modified Files
- `observal-server/models/user.py` — Add `org_id` FK to organizations
- `observal-server/models/mcp.py` — Add `is_private`, `owner_org_id`, `fastmcp_validated`, `download_count`, `unique_agents`
- `observal-server/models/skill.py` — Add `is_private`, `owner_org_id`, `download_count`, `unique_agents`; remove `AgentSkillLink`
- `observal-server/models/hook.py` — Add `git_url`, `is_private`, `owner_org_id`, `download_count`, `unique_agents`; remove `AgentHookLink`
- `observal-server/models/prompt.py` — Add `git_url`, `is_private`, `owner_org_id`, `download_count`, `unique_agents`
- `observal-server/models/sandbox.py` — Add `git_url`, `is_private`, `owner_org_id`, `download_count`, `unique_agents`
- `observal-server/models/agent.py` — Add `git_url`, `is_private`, `owner_org_id`, `download_count`, `unique_users`; remove `AgentMcpLink`; add `components` relationship
- `observal-server/models/feedback.py` — Widen `listing_type` to VARCHAR(50)
- `observal-server/models/submission.py` — Widen `listing_type` to VARCHAR(50)
- `observal-server/models/__init__.py` — Add new exports, remove old ones
- `observal-server/main.py` — Remove tool and graphrag routers

### Deleted Files
- `observal-server/models/tool.py` — Eliminated type
- `observal-server/models/graphrag.py` — Eliminated type

---

### Task 1: Organization Model + User Update

**Files:**
- Create: `observal-server/models/organization.py`
- Modify: `observal-server/models/user.py`
- Test: `tests/test_schema_redesign.py`

- [ ] **Step 1: Write the failing test for Organization model**

Create `tests/test_schema_redesign.py`:

```python
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
        assert any(
            uc for uc in Organization.__table__.constraints
            if hasattr(uc, "columns") and slug_col in uc.columns
        ) or slug_col.unique


class TestUserOrgField:
    def test_user_has_org_id(self):
        from models.user import User
        cols = {c.name for c in User.__table__.columns}
        assert "org_id" in cols

    def test_user_org_id_is_nullable(self):
        from models.user import User
        org_col = User.__table__.c.org_id
        assert org_col.nullable is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models.organization'`

- [ ] **Step 3: Create Organization model**

Create `observal-server/models/organization.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 4: Update User model to add org_id**

Modify `observal-server/models/user.py` — add these imports and column:

```python
import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    developer = "developer"
    user = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestOrganizationModel ../tests/test_schema_redesign.py::TestUserOrgField -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add observal-server/models/organization.py observal-server/models/user.py tests/test_schema_redesign.py
git commit -m "feat(models): add Organization model and org_id to User

Part of #78"
```

---

### Task 2: ComponentSource Model

**Files:**
- Create: `observal-server/models/component_source.py`
- Test: `tests/test_schema_redesign.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_schema_redesign.py`:

```python
class TestComponentSourceModel:
    def test_component_source_tablename(self):
        from models.component_source import ComponentSource
        assert ComponentSource.__tablename__ == "component_sources"

    def test_component_source_has_required_columns(self):
        from models.component_source import ComponentSource
        cols = {c.name for c in ComponentSource.__table__.columns}
        required = {"id", "url", "provider", "component_type", "is_public", "owner_org_id",
                    "auto_sync_interval", "last_synced_at", "sync_status", "sync_error", "created_at"}
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestComponentSourceModel -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models.component_source'`

- [ ] **Step 3: Create ComponentSource model**

Create `observal-server/models/component_source.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Interval, String, Text, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ComponentSource(Base):
    __tablename__ = "component_sources"
    __table_args__ = (
        UniqueConstraint("url", "component_type", name="uq_component_sources_url_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # github, gitlab, bitbucket
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)  # mcp, skill, hook, prompt, sandbox
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    auto_sync_interval: Mapped[str | None] = mapped_column(Interval, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestComponentSourceModel -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add observal-server/models/component_source.py tests/test_schema_redesign.py
git commit -m "feat(models): add ComponentSource model for Git mirroring

Part of #78"
```

---

### Task 3: Update Component Tables (MCP, Skill, Hook, Prompt, Sandbox)

**Files:**
- Modify: `observal-server/models/mcp.py`
- Modify: `observal-server/models/skill.py`
- Modify: `observal-server/models/hook.py`
- Modify: `observal-server/models/prompt.py`
- Modify: `observal-server/models/sandbox.py`
- Test: `tests/test_schema_redesign.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema_redesign.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestComponentTableUpdates -v`
Expected: FAIL — missing columns on most models

- [ ] **Step 3: Update MCP model**

Replace `observal-server/models/mcp.py` with:

```python
import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class ListingStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class McpListing(Base):
    __tablename__ = "mcp_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    git_url: Mapped[str] = mapped_column(String(500), nullable=False)
    git_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    transport: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fastmcp_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    tools_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    setup_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_agents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    validation_results: Mapped[list["McpValidationResult"]] = relationship(
        back_populates="listing", lazy="selectin", cascade="all, delete-orphan"
    )


class McpDownload(Base):
    __tablename__ = "mcp_downloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mcp_listings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ide: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class McpValidationResult(Base):
    __tablename__ = "mcp_validation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mcp_listings.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    listing: Mapped["McpListing"] = relationship(back_populates="validation_results")
```

- [ ] **Step 4: Update Skill model**

Replace `observal-server/models/skill.py` with:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mcp import ListingStatus


class SkillListing(Base):
    __tablename__ = "skill_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    git_url: Mapped[str] = mapped_column(String(500), nullable=False)
    git_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_agents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    skill_path: Mapped[str] = mapped_column(String(500), default="/")
    target_agents: Mapped[list] = mapped_column(JSON, default=list)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    triggers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    slash_command: Mapped[str | None] = mapped_column(String(100), nullable=True)
    has_scripts: Mapped[bool] = mapped_column(Boolean, default=False)
    has_templates: Mapped[bool] = mapped_column(Boolean, default=False)
    is_power: Mapped[bool] = mapped_column(Boolean, default=False)
    power_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    mcp_server_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    activation_keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)


class SkillDownload(Base):
    __tablename__ = "skill_downloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skill_listings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ide: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

- [ ] **Step 5: Update Hook model**

Replace `observal-server/models/hook.py` with:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mcp import ListingStatus


class HookListing(Base):
    __tablename__ = "hook_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    git_url: Mapped[str] = mapped_column(String(500), nullable=False)
    git_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_agents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(10), default="async")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    handler_type: Mapped[str] = mapped_column(String(20), nullable=False)
    handler_config: Mapped[dict] = mapped_column(JSON, default=dict)
    input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scope: Mapped[str] = mapped_column(String(20), default="agent")
    tool_filter: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_pattern: Mapped[list | None] = mapped_column(JSON, nullable=True)


class HookDownload(Base):
    __tablename__ = "hook_downloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hook_listings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ide: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

- [ ] **Step 6: Update Prompt model**

Replace `observal-server/models/prompt.py` with:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mcp import ListingStatus


class PromptListing(Base):
    __tablename__ = "prompt_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    git_url: Mapped[str] = mapped_column(String(500), nullable=False)
    git_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(JSON, default=list)
    model_hints: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_agents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class PromptDownload(Base):
    __tablename__ = "prompt_downloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("prompt_listings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ide: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

- [ ] **Step 7: Update Sandbox model**

Replace `observal-server/models/sandbox.py` with:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mcp import ListingStatus


class SandboxListing(Base):
    __tablename__ = "sandbox_listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    git_url: Mapped[str] = mapped_column(String(500), nullable=False)
    git_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_type: Mapped[str] = mapped_column(String(20), nullable=False)
    image: Mapped[str] = mapped_column(String(500), nullable=False)
    dockerfile_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resource_limits: Mapped[dict] = mapped_column(JSON, default=dict)
    network_policy: Mapped[str] = mapped_column(String(20), default="none")
    allowed_mounts: Mapped[list] = mapped_column(JSON, default=list)
    env_vars: Mapped[dict] = mapped_column(JSON, default=dict)
    entrypoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_agents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class SandboxDownload(Base):
    __tablename__ = "sandbox_downloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sandbox_listings.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ide: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestComponentTableUpdates -v`
Expected: All 17 tests PASS

- [ ] **Step 9: Commit**

```bash
git add observal-server/models/mcp.py observal-server/models/skill.py observal-server/models/hook.py observal-server/models/prompt.py observal-server/models/sandbox.py tests/test_schema_redesign.py
git commit -m "feat(models): add org fields, git_ref, download counts to all component tables

Remove AgentSkillLink and AgentHookLink (replaced by AgentComponent).
Add is_private, owner_org_id, download_count, unique_agents.
Add git_url to hook, prompt, sandbox (mcp and skill already had it).
Add fastmcp_validated and transport to MCP.
Remove McpCustomField (use JSONB instead).

Part of #78"
```

---

### Task 4: Agent Model Update + AgentComponent Junction Table

**Files:**
- Modify: `observal-server/models/agent.py`
- Create: `observal-server/models/agent_component.py`
- Test: `tests/test_schema_redesign.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema_redesign.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestAgentModelUpdate ../tests/test_schema_redesign.py::TestAgentComponentModel -v`
Expected: FAIL

- [ ] **Step 3: Create AgentComponent model**

Create `observal-server/models/agent_component.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AgentComponent(Base):
    __tablename__ = "agent_components"
    __table_args__ = (
        UniqueConstraint("agent_id", "component_type", "component_id",
                         name="uq_agent_components_agent_type_component"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)
    component_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_ref: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    config_override: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

- [ ] **Step 4: Update Agent model**

Replace `observal-server/models/agent.py` with:

```python
import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class AgentStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    git_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    external_mcps: Mapped[list] = mapped_column(JSON, default=list)
    supported_ides: Mapped[list] = mapped_column(JSON, default=list)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    status: Mapped[AgentStatus] = mapped_column(Enum(AgentStatus), default=AgentStatus.active)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_users: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    components: Mapped[list["AgentComponent"]] = relationship(
        back_populates="agent", lazy="selectin", order_by="AgentComponent.order_index",
        cascade="all, delete-orphan"
    )
    goal_template: Mapped["AgentGoalTemplate | None"] = relationship(
        back_populates="agent", lazy="selectin", uselist=False, cascade="all, delete-orphan"
    )


class AgentGoalTemplate(Base):
    __tablename__ = "agent_goal_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    agent: Mapped["Agent"] = relationship(back_populates="goal_template")
    sections: Mapped[list["AgentGoalSection"]] = relationship(
        back_populates="goal_template", lazy="selectin", order_by="AgentGoalSection.order", cascade="all, delete-orphan"
    )


class AgentGoalSection(Base):
    __tablename__ = "agent_goal_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_goal_templates.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    grounding_required: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    goal_template: Mapped["AgentGoalTemplate"] = relationship(back_populates="sections")


from models.agent_component import AgentComponent  # noqa: E402

AgentComponent.agent = relationship("Agent", back_populates="components")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestAgentModelUpdate ../tests/test_schema_redesign.py::TestAgentComponentModel -v`
Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add observal-server/models/agent.py observal-server/models/agent_component.py tests/test_schema_redesign.py
git commit -m "feat(models): add AgentComponent junction table and update Agent model

Replace AgentMcpLink with polymorphic AgentComponent.
Add git_url, is_private, owner_org_id, download_count, unique_users to Agent.
No FK constraint on component_id for future flexibility.

Part of #78"
```

---

### Task 5: Download Tracking Models

**Files:**
- Create: `observal-server/models/download.py`
- Test: `tests/test_schema_redesign.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema_redesign.py`:

```python
class TestDownloadModels:
    def test_agent_download_tablename(self):
        from models.download import AgentDownloadRecord
        assert AgentDownloadRecord.__tablename__ == "agent_download_records"

    def test_agent_download_has_required_columns(self):
        from models.download import AgentDownloadRecord
        cols = {c.name for c in AgentDownloadRecord.__table__.columns}
        required = {"id", "agent_id", "user_id", "fingerprint", "source", "ide", "installed_at"}
        assert required.issubset(cols)

    def test_agent_download_user_id_nullable(self):
        """user_id nullable for anonymous users (fingerprint used instead)."""
        from models.download import AgentDownloadRecord
        col = AgentDownloadRecord.__table__.c.user_id
        assert col.nullable is True

    def test_agent_download_has_unique_constraints(self):
        from models.download import AgentDownloadRecord
        table = AgentDownloadRecord.__table__
        unique_constraints = [
            uc for uc in table.constraints
            if hasattr(uc, "columns") and len(uc.columns) == 2
        ]
        col_sets = [frozenset(c.name for c in uc.columns) for uc in unique_constraints]
        assert frozenset({"agent_id", "user_id"}) in col_sets
        assert frozenset({"agent_id", "fingerprint"}) in col_sets

    def test_component_download_tablename(self):
        from models.download import ComponentDownloadRecord
        assert ComponentDownloadRecord.__tablename__ == "component_download_records"

    def test_component_download_has_required_columns(self):
        from models.download import ComponentDownloadRecord
        cols = {c.name for c in ComponentDownloadRecord.__table__.columns}
        required = {"id", "component_type", "component_id", "version_ref",
                    "agent_id", "source", "downloaded_at"}
        assert required.issubset(cols)

    def test_component_download_no_unique_constraint(self):
        """Component downloads are NOT deduplicated — count every agent pull."""
        from models.download import ComponentDownloadRecord
        table = ComponentDownloadRecord.__table__
        # Should only have PK constraint
        non_pk_unique = [
            uc for uc in table.constraints
            if hasattr(uc, "columns") and len(uc.columns) > 1
        ]
        assert len(non_pk_unique) == 0, "component_download_records should have no multi-column unique constraints"

    def test_component_download_no_fk_on_component_id(self):
        """component_id should NOT have a FK constraint (polymorphic)."""
        from models.download import ComponentDownloadRecord
        col = ComponentDownloadRecord.__table__.c.component_id
        fks = col.foreign_keys
        assert len(fks) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestDownloadModels -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create download models**

Create `observal-server/models/download.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AgentDownloadRecord(Base):
    """Deduplicated download tracking for agents. Same user pulling 15 times = 1 record."""

    __tablename__ = "agent_download_records"
    __table_args__ = (
        UniqueConstraint("agent_id", "user_id", name="uq_agent_downloads_agent_user"),
        UniqueConstraint("agent_id", "fingerprint", name="uq_agent_downloads_agent_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    ide: Mapped[str | None] = mapped_column(String(50), nullable=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ComponentDownloadRecord(Base):
    """Non-deduplicated download tracking for components. Every agent pull creates new records."""

    __tablename__ = "component_download_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)
    component_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_ref: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestDownloadModels -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add observal-server/models/download.py tests/test_schema_redesign.py
git commit -m "feat(models): add AgentDownloadRecord and ComponentDownloadRecord

AgentDownloadRecord: deduplicated by user_id or fingerprint (anonymous).
ComponentDownloadRecord: NOT deduplicated, counts every agent pull.
No FK on component_id (polymorphic reference).

Part of #78"
```

---

### Task 6: ExporterConfig Model

**Files:**
- Create: `observal-server/models/exporter_config.py`
- Test: `tests/test_schema_redesign.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_schema_redesign.py`:

```python
class TestExporterConfigModel:
    def test_exporter_config_tablename(self):
        from models.exporter_config import ExporterConfig
        assert ExporterConfig.__tablename__ == "exporter_configs"

    def test_exporter_config_has_required_columns(self):
        from models.exporter_config import ExporterConfig
        cols = {c.name for c in ExporterConfig.__table__.columns}
        required = {"id", "org_id", "exporter_type", "enabled", "config", "created_at", "updated_at"}
        assert required.issubset(cols)

    def test_exporter_config_unique_per_org(self):
        from models.exporter_config import ExporterConfig
        table = ExporterConfig.__table__
        unique_constraints = [
            uc for uc in table.constraints
            if hasattr(uc, "columns") and len(uc.columns) == 2
        ]
        col_sets = [frozenset(c.name for c in uc.columns) for uc in unique_constraints]
        assert frozenset({"org_id", "exporter_type"}) in col_sets
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestExporterConfigModel -v`
Expected: FAIL

- [ ] **Step 3: Create ExporterConfig model**

Create `observal-server/models/exporter_config.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ExporterConfig(Base):
    __tablename__ = "exporter_configs"
    __table_args__ = (
        UniqueConstraint("org_id", "exporter_type", name="uq_exporter_configs_org_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    exporter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestExporterConfigModel -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add observal-server/models/exporter_config.py tests/test_schema_redesign.py
git commit -m "feat(models): add ExporterConfig model for telemetry export

Supports grafana, datadog, loki, otel exporter types.
Unique per org + exporter type.

Part of #78"
```

---

### Task 7: Remove Tool and GraphRAG Models + Update Wiring

**Files:**
- Delete: `observal-server/models/tool.py`
- Delete: `observal-server/models/graphrag.py`
- Modify: `observal-server/models/__init__.py`
- Modify: `observal-server/main.py`
- Modify: `observal-server/models/feedback.py`
- Modify: `observal-server/models/submission.py`
- Test: `tests/test_schema_redesign.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema_redesign.py`:

```python
class TestRemovedTypes:
    def test_tool_listing_not_importable(self):
        """ToolListing should no longer exist in models.__init__."""
        import models
        assert not hasattr(models, "ToolListing")
        assert not hasattr(models, "ToolDownload")

    def test_graphrag_listing_not_importable(self):
        """GraphRagListing should no longer exist in models.__init__."""
        import models
        assert not hasattr(models, "GraphRagListing")
        assert not hasattr(models, "GraphRagDownload")

    def test_new_models_importable(self):
        """All new models should be importable from models package."""
        from models import (
            Organization, ComponentSource, AgentComponent,
            AgentDownloadRecord, ComponentDownloadRecord, ExporterConfig,
        )
        assert Organization.__tablename__ == "organizations"
        assert ComponentSource.__tablename__ == "component_sources"
        assert AgentComponent.__tablename__ == "agent_components"
        assert AgentDownloadRecord.__tablename__ == "agent_download_records"
        assert ComponentDownloadRecord.__tablename__ == "component_download_records"
        assert ExporterConfig.__tablename__ == "exporter_configs"


class TestFeedbackSubmissionUpdates:
    def test_feedback_listing_type_wider(self):
        from models.feedback import Feedback
        col = Feedback.__table__.c.listing_type
        assert col.type.length >= 50

    def test_submission_listing_type_wider(self):
        from models.submission import Submission
        col = Submission.__table__.c.listing_type
        assert col.type.length >= 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestRemovedTypes ../tests/test_schema_redesign.py::TestFeedbackSubmissionUpdates -v`
Expected: FAIL

- [ ] **Step 3: Delete tool.py and graphrag.py**

```bash
rm observal-server/models/tool.py
rm observal-server/models/graphrag.py
```

- [ ] **Step 4: Update feedback.py — widen listing_type**

Replace `observal-server/models/feedback.py` with:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedback_rating"),
        Index("ix_feedback_listing", "listing_id", "listing_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    listing_type: Mapped[str] = mapped_column(String(50), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

- [ ] **Step 5: Update submission.py — widen listing_type**

Replace `observal-server/models/submission.py` with:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mcp import ListingStatus


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_type: Mapped[str] = mapped_column(String(50), nullable=False)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 6: Update models/__init__.py**

Replace `observal-server/models/__init__.py` with:

```python
from models.agent import Agent, AgentGoalSection, AgentGoalTemplate, AgentStatus
from models.agent_component import AgentComponent
from models.alert import AlertRule
from models.base import Base
from models.component_source import ComponentSource
from models.download import AgentDownloadRecord, ComponentDownloadRecord
from models.enterprise_config import EnterpriseConfig
from models.eval import EvalRun, EvalRunStatus, Scorecard, ScorecardDimension
from models.exporter_config import ExporterConfig
from models.feedback import Feedback
from models.hook import HookDownload, HookListing
from models.mcp import ListingStatus, McpDownload, McpListing, McpValidationResult
from models.organization import Organization
from models.prompt import PromptDownload, PromptListing
from models.sandbox import SandboxDownload, SandboxListing
from models.scoring import (
    DEFAULT_DIMENSION_WEIGHTS,
    DEFAULT_PENALTIES,
    DimensionWeight,
    PenaltyDefinition,
    PenaltySeverity,
    PenaltyTriggerType,
    ScoringDimension,
    TracePenalty,
)
from models.skill import SkillDownload, SkillListing
from models.submission import Submission
from models.user import User, UserRole

__all__ = [
    "DEFAULT_DIMENSION_WEIGHTS",
    "DEFAULT_PENALTIES",
    "Agent",
    "AgentComponent",
    "AgentDownloadRecord",
    "AgentGoalSection",
    "AgentGoalTemplate",
    "AgentStatus",
    "AlertRule",
    "Base",
    "ComponentDownloadRecord",
    "ComponentSource",
    "DimensionWeight",
    "EnterpriseConfig",
    "EvalRun",
    "EvalRunStatus",
    "ExporterConfig",
    "Feedback",
    "HookDownload",
    "HookListing",
    "ListingStatus",
    "McpDownload",
    "McpListing",
    "McpValidationResult",
    "Organization",
    "PenaltyDefinition",
    "PenaltySeverity",
    "PenaltyTriggerType",
    "PromptDownload",
    "PromptListing",
    "SandboxDownload",
    "SandboxListing",
    "Scorecard",
    "ScorecardDimension",
    "ScoringDimension",
    "SkillDownload",
    "SkillListing",
    "Submission",
    "TracePenalty",
    "User",
    "UserRole",
]
```

- [ ] **Step 7: Update main.py — remove tool and graphrag routers**

In `observal-server/main.py`, remove these two import lines:
```python
from api.routes.graphrag import router as graphrag_router
from api.routes.tool import router as tool_router
```

And remove these two `include_router` lines:
```python
app.include_router(tool_router)
app.include_router(graphrag_router)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py::TestRemovedTypes ../tests/test_schema_redesign.py::TestFeedbackSubmissionUpdates -v`
Expected: All 5 tests PASS

- [ ] **Step 9: Run all schema redesign tests**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/test_schema_redesign.py -v`
Expected: All tests PASS (approximately 49 tests)

- [ ] **Step 10: Commit**

```bash
git rm observal-server/models/tool.py observal-server/models/graphrag.py
git add observal-server/models/__init__.py observal-server/models/feedback.py observal-server/models/submission.py observal-server/main.py tests/test_schema_redesign.py
git commit -m "feat(models): remove tool/graphrag types, update wiring

Delete ToolListing, ToolDownload, GraphRagListing, GraphRagDownload.
Remove tool and graphrag routers from main.py.
Widen listing_type to VARCHAR(50) in feedback and submission.
Update models/__init__.py with all new exports.

Part of #78"
```

---

### Task 8: Verify Full Test Suite

**Files:**
- Test: all existing tests

- [ ] **Step 1: Run the full test suite**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/ -v --tb=short 2>&1 | tail -50`
Expected: Some existing tests may fail due to removed models (ToolListing, GraphRagListing, AgentMcpLink, etc.)

- [ ] **Step 2: Fix test_registry_types.py**

Tests in `tests/test_registry_types.py` reference `ToolListing`, `ToolDownload`, `GraphRagListing`, `GraphRagDownload`, `AgentSkillLink`, `AgentHookLink`. Remove or update those test classes:
- Delete all `TestModels` tests for `tool_*` and `graphrag_*` tablenames
- Delete all route tests for tool and graphrag endpoints
- Delete tests for `AgentSkillLink` and `AgentHookLink`
- Keep tests for remaining types (mcp, skill, hook, prompt, sandbox)

The exact changes depend on which tests fail — read the error output and remove/update the failing references.

- [ ] **Step 3: Fix any other failing tests**

Scan test output for imports of:
- `ToolListing`, `ToolDownload` → delete those test lines
- `GraphRagListing`, `GraphRagDownload` → delete those test lines
- `AgentMcpLink` → replace with `AgentComponent` references
- `AgentSkillLink`, `AgentHookLink` → delete those test lines
- `McpCustomField` → delete those test lines

- [ ] **Step 4: Run full test suite again**

Run: `cd /home/haz3/code/blazeup/Observal && cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/ -v --tb=short 2>&1 | tail -50`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "fix(tests): update existing tests for schema redesign

Remove tests for deleted types (tool, graphrag).
Update tests referencing AgentMcpLink, AgentSkillLink, AgentHookLink.

Part of #78"
```
