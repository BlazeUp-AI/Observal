# Enterprise Mode PR1: Alembic + RBAC Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize Alembic migrations, upgrade from 3-tier to 4-tier RBAC (super_admin > admin > reviewer > user), add is_demo flag, add deployment config, and replace all inline role checks with a hierarchy-aware `require_role` dependency.

**Architecture:** The UserRole enum gains `super_admin` and renames `developer` → `reviewer`. A new `require_role(min_role)` FastAPI dependency replaces the existing unused decorator and all inline `_require_admin()` calls. Alembic is initialized from scratch with an async PostgreSQL driver. `create_all()` is kept for development; Alembic handles production migrations.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy (async), Alembic, PostgreSQL, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-04-13-enterprise-mode-design.md`

**Branch:** `feat/enterprise-deployment-mode` (create from current `fix/db-consistency-audit`)

**DCO:** All commits MUST use `-s` flag for sign-off.

---

### Task 1: Initialize Alembic with async PostgreSQL support

**Context:** The project has no migration infrastructure. Schema is managed via `Base.metadata.create_all()` at startup. We need Alembic for the role enum migration and all future schema changes. Alembic is already a dependency in `observal-server/pyproject.toml`.

**Files:**
**Design note:** The spec calls for a "baseline migration capturing full current schema." We intentionally skip this because `Base.metadata.create_all()` remains in the lifespan for development. Alembic starts with the role enum migration (Task 3) as its first revision. On existing databases, `alembic upgrade head` applies only schema changes. On new databases, `create_all()` builds tables and Alembic handles incremental changes. All migrations use idempotent SQL (`IF NOT EXISTS` / `IF EXISTS`) so either order is safe.

**Files:**
- Create: `observal-server/alembic.ini`
- Create: `observal-server/alembic/env.py`
- Create: `observal-server/alembic/script.py.mako`
- Create: `observal-server/alembic/versions/` (empty directory)

- [ ] **Step 1: Initialize Alembic with async template**

Run from `observal-server/`:
```bash
cd observal-server && uv run alembic init -t async alembic
```

This creates `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, and `alembic/versions/`.

- [ ] **Step 2: Configure alembic.ini**

Edit `observal-server/alembic.ini`. The key change is setting a placeholder URL (env.py will override it from config.py):

```ini
# Alembic Configuration
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/observal

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Configure env.py for async + model imports**

Replace `observal-server/alembic/env.py` with:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from config import settings

# Alembic Config object
config = context.config

# Override URL from application settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so metadata is populated
from models import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Verify Alembic can see models**

Run from `observal-server/`:
```bash
uv run alembic heads
```

Expected: No errors, shows "(head)" or empty (no migrations yet).

- [ ] **Step 5: Commit**

```bash
git add observal-server/alembic.ini observal-server/alembic/
git commit -s -m "$(cat <<'EOF'
feat(db): initialize Alembic with async PostgreSQL support

Set up Alembic migration infrastructure using the async template.
Configured env.py to read DATABASE_URL from application settings
and import all ORM models for autogeneration support.
EOF
)"
```

---

### Task 2: Update UserRole enum and User model

**Context:** Current roles are `admin`, `developer`, `user`. We need to add `super_admin`, rename `developer` → `reviewer`, and add `is_demo` boolean column. The Python model changes first; the Alembic migration (Task 3) handles existing databases.

**Files:**
- Test: `observal-server/tests/test_rbac.py` (create)
- Modify: `observal-server/models/user.py`

- [ ] **Step 1: Write failing test for new enum values**

Create `observal-server/tests/test_rbac.py`:

```python
"""Tests for the 4-tier RBAC system."""

from models.user import User, UserRole


def test_userrole_enum_has_four_tiers():
    """UserRole must have exactly super_admin, admin, reviewer, user."""
    expected = {"super_admin", "admin", "reviewer", "user"}
    actual = {r.value for r in UserRole}
    assert actual == expected, f"Expected {expected}, got {actual}"


def test_userrole_enum_values():
    """Each role's .value matches its name."""
    assert UserRole.super_admin.value == "super_admin"
    assert UserRole.admin.value == "admin"
    assert UserRole.reviewer.value == "reviewer"
    assert UserRole.user.value == "user"


def test_developer_role_does_not_exist():
    """The old 'developer' role must not exist."""
    assert not hasattr(UserRole, "developer"), "developer role should be removed"


def test_user_model_has_is_demo_field():
    """User model must have is_demo boolean field."""
    user = User(
        email="test@example.com",
        name="Test",
        api_key_hash="a" * 64,
    )
    assert user.is_demo is False, "is_demo should default to False"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd observal-server && uv run pytest tests/test_rbac.py -v
```

Expected: FAIL — `UserRole` has no `super_admin` or `reviewer`, has `developer`, and `User` has no `is_demo`.

- [ ] **Step 3: Update UserRole enum and User model**

Edit `observal-server/models/user.py`:

Replace the `UserRole` enum:
```python
class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    admin = "admin"
    reviewer = "reviewer"
    user = "user"
```

Add `is_demo` column to the `User` class, after `created_at`:
```python
    is_demo: Mapped[bool] = mapped_column(default=False, server_default="false")
```

Add the `Boolean` import from sqlalchemy:
```python
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd observal-server && uv run pytest tests/test_rbac.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add observal-server/models/user.py observal-server/tests/test_rbac.py
git commit -s -m "$(cat <<'EOF'
feat(rbac): upgrade UserRole to 4-tier hierarchy with is_demo flag

Replace 3-tier (admin/developer/user) with 4-tier
(super_admin/admin/reviewer/user). Rename developer → reviewer.
Add is_demo boolean column to User model for demo account tracking.
EOF
)"
```

---

### Task 3: Create Alembic migration for role enum changes + is_demo

**Context:** Existing databases have the old 3-value enum and no `is_demo` column. This migration handles the transition. Uses `IF NOT EXISTS` / `IF EXISTS` guards for idempotency — safe whether database was created by `create_all()` (new schema) or is an existing database (old schema).

**Files:**
- Create: `observal-server/alembic/versions/0001_add_rbac_roles_and_is_demo.py`

- [ ] **Step 1: Create the migration file**

Create `observal-server/alembic/versions/0001_add_rbac_roles_and_is_demo.py`:

```python
"""Add super_admin and reviewer roles, rename developer to reviewer, add is_demo column.

Revision ID: 0001
Revises:
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values (idempotent — safe on fresh databases)
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'reviewer'")

    # Rename developer -> reviewer in existing rows
    # (PostgreSQL doesn't support renaming enum values, but we can update rows)
    op.execute("UPDATE users SET role = 'reviewer' WHERE role = 'developer'")

    # Add is_demo column (idempotent via IF NOT EXISTS pattern)
    # Use raw SQL for IF NOT EXISTS since op.add_column doesn't support it
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'is_demo'
            ) THEN
                ALTER TABLE users ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT false;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # Drop is_demo column
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'is_demo'
            ) THEN
                ALTER TABLE users DROP COLUMN is_demo;
            END IF;
        END
        $$;
    """)

    # Rename reviewer back to developer in rows
    op.execute("UPDATE users SET role = 'developer' WHERE role = 'reviewer'")

    # Note: PostgreSQL doesn't support removing enum values.
    # 'super_admin' and 'reviewer' will remain in the enum type but won't be used.
```

- [ ] **Step 2: Verify migration file is detected**

```bash
cd observal-server && uv run alembic heads
```

Expected: Shows `0001 (head)`.

- [ ] **Step 3: Also update _ensure_columns for the transition period**

Edit `observal-server/main.py` — add `is_demo` to the `_ensure_columns` function so existing databases that haven't run Alembic yet still get the column:

```python
async def _ensure_columns(conn):
    """Add columns that may be missing on existing databases."""
    from sqlalchemy import text

    try:
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)"))
    except Exception:
        pass
    try:
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT false"))
    except Exception:
        pass
```

- [ ] **Step 4: Commit**

```bash
git add observal-server/alembic/versions/0001_add_rbac_roles_and_is_demo.py observal-server/main.py
git commit -s -m "$(cat <<'EOF'
feat(db): add Alembic migration for 4-tier RBAC enum and is_demo column

Migration adds super_admin and reviewer to userrole enum, renames
existing developer rows to reviewer, and adds is_demo boolean column.
All operations are idempotent for safety on fresh and existing databases.
EOF
)"
```

---

### Task 4: Add deployment mode and demo account config

**Context:** `config.py` needs `DEPLOYMENT_MODE` and 8 `DEMO_*` env vars. These are read by later PRs (demo seeding, route guards) but the config should be in place now.

**Files:**
- Test: `observal-server/tests/test_config.py` (create)
- Modify: `observal-server/config.py`

- [ ] **Step 1: Write failing test for new config vars**

Create `observal-server/tests/test_config.py`:

```python
"""Tests for configuration settings."""

import os


def test_deployment_mode_defaults_to_local():
    """DEPLOYMENT_MODE should default to 'local'."""
    # Import fresh to pick up defaults
    from config import Settings

    s = Settings(
        DATABASE_URL="sqlite+aiosqlite:///",
        SECRET_KEY="test",
    )
    assert s.DEPLOYMENT_MODE == "local"


def test_deployment_mode_reads_env(monkeypatch):
    """DEPLOYMENT_MODE should read from environment."""
    monkeypatch.setenv("DEPLOYMENT_MODE", "enterprise")
    from config import Settings

    s = Settings(
        DATABASE_URL="sqlite+aiosqlite:///",
        SECRET_KEY="test",
        DEPLOYMENT_MODE="enterprise",
    )
    assert s.DEPLOYMENT_MODE == "enterprise"


def test_demo_env_vars_default_to_none():
    """All DEMO_* vars should default to None."""
    from config import Settings

    s = Settings(
        DATABASE_URL="sqlite+aiosqlite:///",
        SECRET_KEY="test",
    )
    assert s.DEMO_SUPER_ADMIN_EMAIL is None
    assert s.DEMO_SUPER_ADMIN_PASSWORD is None
    assert s.DEMO_ADMIN_EMAIL is None
    assert s.DEMO_ADMIN_PASSWORD is None
    assert s.DEMO_REVIEWER_EMAIL is None
    assert s.DEMO_REVIEWER_PASSWORD is None
    assert s.DEMO_USER_EMAIL is None
    assert s.DEMO_USER_PASSWORD is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd observal-server && uv run pytest tests/test_config.py -v
```

Expected: FAIL — `Settings` has no `DEPLOYMENT_MODE` or `DEMO_*` attributes.

- [ ] **Step 3: Add new settings**

Edit `observal-server/config.py`. Add after the rate limiting settings (before `model_config`):

```python
    # Deployment mode
    DEPLOYMENT_MODE: str = "local"  # "local" | "enterprise"

    # Demo accounts (seeded on first startup if set and no real users exist)
    DEMO_SUPER_ADMIN_EMAIL: str | None = None
    DEMO_SUPER_ADMIN_PASSWORD: str | None = None
    DEMO_ADMIN_EMAIL: str | None = None
    DEMO_ADMIN_PASSWORD: str | None = None
    DEMO_REVIEWER_EMAIL: str | None = None
    DEMO_REVIEWER_PASSWORD: str | None = None
    DEMO_USER_EMAIL: str | None = None
    DEMO_USER_PASSWORD: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd observal-server && uv run pytest tests/test_config.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add observal-server/config.py observal-server/tests/test_config.py
git commit -s -m "$(cat <<'EOF'
feat(config): add DEPLOYMENT_MODE and demo account env vars

Add DEPLOYMENT_MODE (local|enterprise, defaults to local) and 8
DEMO_* env vars for seeding demo accounts on first startup.
EOF
)"
```

---

### Task 5: Refactor require_role to hierarchy-aware FastAPI dependency

**Context:** The current `require_role` in `deps.py` is an unused decorator (lines 73-82) with a bug (unreachable `return`). Replace it with a hierarchy-aware FastAPI dependency that returns the authenticated user. Routes use it via `Depends(require_role(UserRole.admin))`.

**Files:**
- Test: `observal-server/tests/test_rbac.py` (append)
- Modify: `observal-server/api/deps.py`

- [ ] **Step 1: Write failing tests for hierarchy-aware require_role**

Append to `observal-server/tests/test_rbac.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from api.deps import require_role, ROLE_HIERARCHY


def test_role_hierarchy_ordering():
    """super_admin has lowest number (highest privilege)."""
    assert ROLE_HIERARCHY[UserRole.super_admin] < ROLE_HIERARCHY[UserRole.admin]
    assert ROLE_HIERARCHY[UserRole.admin] < ROLE_HIERARCHY[UserRole.reviewer]
    assert ROLE_HIERARCHY[UserRole.reviewer] < ROLE_HIERARCHY[UserRole.user]


def test_role_hierarchy_has_all_roles():
    """Every UserRole must be in the hierarchy."""
    for role in UserRole:
        assert role in ROLE_HIERARCHY, f"{role} missing from ROLE_HIERARCHY"


@pytest.mark.asyncio
async def test_require_role_allows_exact_match():
    """User with exact required role should pass."""
    dep = require_role(UserRole.admin)
    mock_user = MagicMock()
    mock_user.role = UserRole.admin
    result = await dep(current_user=mock_user)
    assert result is mock_user


@pytest.mark.asyncio
async def test_require_role_allows_higher_role():
    """super_admin should pass an admin check."""
    dep = require_role(UserRole.admin)
    mock_user = MagicMock()
    mock_user.role = UserRole.super_admin
    result = await dep(current_user=mock_user)
    assert result is mock_user


@pytest.mark.asyncio
async def test_require_role_blocks_lower_role():
    """user should not pass an admin check."""
    dep = require_role(UserRole.admin)
    mock_user = MagicMock()
    mock_user.role = UserRole.user
    with pytest.raises(HTTPException) as exc_info:
        await dep(current_user=mock_user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_reviewer_allows_admin():
    """admin should pass a reviewer check."""
    dep = require_role(UserRole.reviewer)
    mock_user = MagicMock()
    mock_user.role = UserRole.admin
    result = await dep(current_user=mock_user)
    assert result is mock_user


@pytest.mark.asyncio
async def test_require_role_reviewer_blocks_user():
    """user should not pass a reviewer check."""
    dep = require_role(UserRole.reviewer)
    mock_user = MagicMock()
    mock_user.role = UserRole.user
    with pytest.raises(HTTPException) as exc_info:
        await dep(current_user=mock_user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_user_allows_everyone():
    """Every role should pass a user-level check."""
    dep = require_role(UserRole.user)
    for role in UserRole:
        mock_user = MagicMock()
        mock_user.role = role
        result = await dep(current_user=mock_user)
        assert result is mock_user
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd observal-server && uv run pytest tests/test_rbac.py -v
```

Expected: FAIL — `ROLE_HIERARCHY` not importable, `require_role` doesn't work as a dependency.

- [ ] **Step 3: Implement hierarchy-aware require_role**

Edit `observal-server/api/deps.py`. Replace the existing `require_role` function (lines 73-82) with:

```python
# Role hierarchy: lower number = higher privilege
ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.super_admin: 0,
    UserRole.admin: 1,
    UserRole.reviewer: 2,
    UserRole.user: 3,
}


def require_role(min_role: UserRole):
    """FastAPI dependency that requires the user to have at least the given role level.

    Usage: current_user: User = Depends(require_role(UserRole.admin))
    """

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(current_user.role, 999)
        required_level = ROLE_HIERARCHY[min_role]
        if user_level > required_level:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return _check


# Convenience shorthand for super_admin-only endpoints
require_super_admin = require_role(UserRole.super_admin)
```

Also remove the `functools.wraps` import from the top of the file (line 4) since the old decorator pattern is gone.

**Note:** `require_super_admin` is a pre-built dependency for future destructive endpoints (data wipe, org deletion). No routes use it in PR1, but it's defined here so it's importable when needed.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd observal-server && uv run pytest tests/test_rbac.py -v
```

Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add observal-server/api/deps.py observal-server/tests/test_rbac.py
git commit -s -m "$(cat <<'EOF'
feat(rbac): implement hierarchy-aware require_role FastAPI dependency

Replace the unused role decorator with a dependency-based approach.
require_role(min_role) returns a FastAPI Depends that checks the
user's role against a hierarchy: super_admin > admin > reviewer > user.
EOF
)"
```

---

### Task 6: Refactor admin.py — replace inline _require_admin with require_role

**Context:** `api/routes/admin.py` has 17 endpoints that all call `_require_admin(current_user)` in the function body. Replace every instance with `Depends(require_role(UserRole.admin))` in the function signature. Remove the `_require_admin` helper.

**Files:**
- Modify: `observal-server/api/routes/admin.py`

- [ ] **Step 1: Read the current file**

Read `observal-server/api/routes/admin.py` to identify all `_require_admin(current_user)` calls and the current import of `get_current_user`.

- [ ] **Step 2: Update imports**

In `observal-server/api/routes/admin.py`, change the import:

```python
# Old:
from api.deps import get_current_user, get_db
# New:
from api.deps import get_db, require_role
```

Also ensure `UserRole` is imported:
```python
from models.user import User, UserRole
```

- [ ] **Step 3: Remove the _require_admin function**

Delete the `_require_admin` function (around lines 27-29):
```python
# DELETE THIS:
def _require_admin(user: User):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
```

- [ ] **Step 4: Replace all endpoint signatures**

For every endpoint in admin.py, change the `current_user` parameter and remove the `_require_admin()` call. The pattern for each endpoint is:

```python
# Old pattern:
async def endpoint_name(
    ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    ...

# New pattern:
async def endpoint_name(
    ...,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    ...
```

Apply this to ALL endpoints in admin.py:
1. `list_settings` 
2. `get_setting`
3. `upsert_setting`
4. `delete_setting`
5. `list_users`
6. `create_user`
7. `update_user_role`
8. `reset_user_password`
9. `list_penalties`
10. `update_penalty`
11. `list_weights`
12. `set_global_weights`
13. `set_agent_weights`
14. `create_canary`
15. `list_canaries`
16. `list_canary_reports`
17. `delete_canary`

- [ ] **Step 5: Verify no references to _require_admin remain**

```bash
cd observal-server && grep -rn "_require_admin" api/routes/admin.py
```

Expected: No output (zero matches).

- [ ] **Step 6: Verify no references to get_current_user remain**

```bash
cd observal-server && grep -rn "get_current_user" api/routes/admin.py
```

Expected: No output (zero matches).

- [ ] **Step 7: Run linter**

```bash
cd observal-server && uv run ruff check api/routes/admin.py --fix
```

Expected: No errors (or auto-fixed import ordering).

- [ ] **Step 8: Commit**

```bash
git add observal-server/api/routes/admin.py
git commit -s -m "$(cat <<'EOF'
refactor(admin): replace inline _require_admin with require_role dependency

All 17 admin endpoints now use Depends(require_role(UserRole.admin))
instead of calling _require_admin() in the function body. This means
super_admin also passes admin checks via the role hierarchy.
EOF
)"
```

---

### Task 7: Refactor review.py — replace inline _require_admin with require_role(reviewer)

**Context:** `api/routes/review.py` has its own `_require_admin` function and 4 endpoints using it. Per the spec, review endpoints should require `reviewer` role (not admin), since the new `reviewer` role is purpose-built for this. Admin and super_admin still pass due to hierarchy.

**Files:**
- Modify: `observal-server/api/routes/review.py`

- [ ] **Step 1: Read the current file**

Read `observal-server/api/routes/review.py` to identify all `_require_admin(current_user)` calls and current imports.

- [ ] **Step 2: Update imports**

```python
# Old:
from api.deps import get_current_user, get_db
# New:
from api.deps import get_db, require_role
```

Ensure `UserRole` is imported:
```python
from models.user import User, UserRole
```

- [ ] **Step 3: Remove the _require_admin function**

Delete the `_require_admin` function (around lines 25-27).

- [ ] **Step 4: Replace all endpoint signatures**

Change all 4 endpoints from `Depends(get_current_user)` + `_require_admin()` to `Depends(require_role(UserRole.reviewer))`:

```python
# New pattern for all review endpoints:
async def endpoint_name(
    ...,
    current_user: User = Depends(require_role(UserRole.reviewer)),
    db: AsyncSession = Depends(get_db),
):
    # No _require_admin call needed
    ...
```

Apply to: `list_pending`, `get_review`, `approve`, `reject`.

- [ ] **Step 5: Verify no references to _require_admin or get_current_user remain**

```bash
cd observal-server && grep -rn "_require_admin\|get_current_user" api/routes/review.py
```

Expected: No output.

- [ ] **Step 6: Run linter**

```bash
cd observal-server && uv run ruff check api/routes/review.py --fix
```

- [ ] **Step 7: Commit**

```bash
git add observal-server/api/routes/review.py
git commit -s -m "$(cat <<'EOF'
refactor(review): use require_role(reviewer) for review endpoints

Review endpoints now require reviewer role (previously required admin).
The new reviewer role is purpose-built for component review workflows.
Admin and super_admin pass via role hierarchy.
EOF
)"
```

---

### Task 8: Add require_role(admin) to admin-level route files

**Context:** These route files currently have NO role checks — any authenticated user can access them. Per the spec, they require admin-level access: `telemetry.py` (viewing all traces), `eval.py`, `otel_dashboard.py`, `dashboard.py`.

**Files:**
- Modify: `observal-server/api/routes/telemetry.py`
- Modify: `observal-server/api/routes/eval.py`
- Modify: `observal-server/api/routes/otel_dashboard.py`
- Modify: `observal-server/api/routes/dashboard.py`

- [ ] **Step 1: Read all four files**

Read each file to identify the current import pattern and all endpoints that use `get_current_user`.

- [ ] **Step 2: Apply the same pattern to all four files**

For each file:

1. **Update imports** — replace `get_current_user` with `require_role` in the import from `api.deps`. Add `UserRole` import from `models.user` if not already present.

2. **Update all endpoint signatures** — change every `current_user: User = Depends(get_current_user)` to `current_user: User = Depends(require_role(UserRole.admin))`.

The mechanical change for each endpoint:
```python
# Old:
async def endpoint(current_user: User = Depends(get_current_user), ...):

# New:
async def endpoint(current_user: User = Depends(require_role(UserRole.admin)), ...):
```

- [ ] **Step 3: Verify no get_current_user references remain in these files**

```bash
cd observal-server && grep -rn "get_current_user" api/routes/telemetry.py api/routes/eval.py api/routes/otel_dashboard.py api/routes/dashboard.py
```

Expected: No output.

- [ ] **Step 4: Run linter on all four files**

```bash
cd observal-server && uv run ruff check api/routes/telemetry.py api/routes/eval.py api/routes/otel_dashboard.py api/routes/dashboard.py --fix
```

- [ ] **Step 5: Commit**

```bash
git add observal-server/api/routes/telemetry.py observal-server/api/routes/eval.py observal-server/api/routes/otel_dashboard.py observal-server/api/routes/dashboard.py
git commit -s -m "$(cat <<'EOF'
feat(rbac): add admin role requirement to telemetry, eval, otel, dashboard routes

These routes previously had no role checks — any authenticated user
could access them. Now require admin role for viewing all traces,
running evals, accessing OTEL dashboard, and dashboard queries.
EOF
)"
```

---

### Task 9: Add require_role(user) to resource-level route files

**Context:** These route files currently have NO role checks. Per the spec, they require at least `user` role (which all authenticated users have). This replaces bare `get_current_user` with `require_role(UserRole.user)` — functionally equivalent now but enforces the role hierarchy framework for when roles become more granular.

**Files:**
- Modify: `observal-server/api/routes/agent.py`
- Modify: `observal-server/api/routes/skill.py`
- Modify: `observal-server/api/routes/hook.py`
- Modify: `observal-server/api/routes/prompt.py`
- Modify: `observal-server/api/routes/sandbox.py`
- Modify: `observal-server/api/routes/scan.py`
- Modify: `observal-server/api/routes/mcp.py`
- Modify: `observal-server/api/routes/component_source.py`
- Modify: `observal-server/api/routes/feedback.py`
- Modify: `observal-server/api/routes/alert.py`

- [ ] **Step 1: Read all ten files**

Read each file to identify import patterns and all endpoints using `get_current_user`.

- [ ] **Step 2: Apply the same pattern to all ten files**

For each file:

1. **Update imports** — replace `get_current_user` with `require_role`. Add `UserRole` import if missing.

2. **Update all endpoint signatures** — change every `current_user: User = Depends(get_current_user)` to `current_user: User = Depends(require_role(UserRole.user))`.

```python
# Old:
async def endpoint(current_user: User = Depends(get_current_user), ...):

# New:
async def endpoint(current_user: User = Depends(require_role(UserRole.user)), ...):
```

**Important:** Some endpoints may not have a `current_user` parameter at all (public endpoints). Leave those unchanged. Only modify endpoints that currently depend on `get_current_user`.

- [ ] **Step 3: Check if get_current_user is still used anywhere in route files**

```bash
cd observal-server && grep -rn "get_current_user" api/routes/
```

Expected: Only `api/routes/auth.py` should still use `get_current_user` (auth endpoints handle their own authentication logic and should not go through role checks).

- [ ] **Step 4: Run linter on all modified files**

```bash
cd observal-server && uv run ruff check api/routes/ --fix
```

- [ ] **Step 5: Commit**

```bash
git add observal-server/api/routes/agent.py observal-server/api/routes/skill.py observal-server/api/routes/hook.py observal-server/api/routes/prompt.py observal-server/api/routes/sandbox.py observal-server/api/routes/scan.py observal-server/api/routes/mcp.py observal-server/api/routes/component_source.py observal-server/api/routes/feedback.py observal-server/api/routes/alert.py
git commit -s -m "$(cat <<'EOF'
feat(rbac): add user role requirement to all resource route files

All resource endpoints (agents, skills, hooks, prompts, sandboxes,
scans, MCPs, components, feedback, alerts) now use
require_role(UserRole.user) instead of bare get_current_user.
Functionally equivalent for now but enforces the role hierarchy.
EOF
)"
```

---

### Task 10: Verify get_current_user is only used in auth.py and deps.py

**Context:** After Tasks 6-9, the only files that should still reference `get_current_user` directly are `api/deps.py` (where it's defined) and `api/routes/auth.py` (where auth endpoints handle their own logic). This task verifies the refactor is complete.

**Files:** None (verification only)

- [ ] **Step 1: Search for remaining get_current_user usage**

```bash
cd observal-server && grep -rn "get_current_user" --include="*.py"
```

Expected output should only show:
- `api/deps.py` — definition and use inside `require_role`
- `api/routes/auth.py` — auth endpoints that handle their own auth logic

If any other file appears, go back and fix it.

- [ ] **Step 2: Search for any remaining _require_admin**

```bash
cd observal-server && grep -rn "_require_admin" --include="*.py"
```

Expected: No output (zero matches anywhere).

- [ ] **Step 3: Run all existing tests**

```bash
cd observal-server && uv run pytest tests/ -v
```

Expected: All tests pass. The RBAC tests from Task 2 and Task 5 should all pass.

- [ ] **Step 4: Run ruff on entire codebase**

```bash
cd /home/haz3/code/blazeup/Observal && uv run ruff check observal-server/ --fix
```

Expected: Clean or only pre-existing issues.

- [ ] **Step 5: Run the root test suite**

```bash
cd /home/haz3/code/blazeup/Observal && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich pytest tests/ -q
```

Expected: All existing tests still pass (no regressions from role rename or import changes).

- [ ] **Step 6: Final commit if any lint fixes were needed**

Only if ruff made changes:
```bash
git add -u
git commit -s -m "$(cat <<'EOF'
style: fix lint issues from RBAC refactor
EOF
)"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `observal-server/alembic.ini` | New — Alembic configuration |
| `observal-server/alembic/env.py` | New — async migration runner with model imports |
| `observal-server/alembic/script.py.mako` | New — migration template |
| `observal-server/alembic/versions/0001_*.py` | New — role enum + is_demo migration |
| `observal-server/models/user.py` | Modified — 4-tier UserRole, is_demo column |
| `observal-server/config.py` | Modified — DEPLOYMENT_MODE, DEMO_* vars |
| `observal-server/api/deps.py` | Modified — hierarchy-aware require_role dependency |
| `observal-server/main.py` | Modified — is_demo in _ensure_columns |
| `observal-server/api/routes/admin.py` | Modified — require_role(admin), remove _require_admin |
| `observal-server/api/routes/review.py` | Modified — require_role(reviewer), remove _require_admin |
| `observal-server/api/routes/telemetry.py` | Modified — require_role(admin) |
| `observal-server/api/routes/eval.py` | Modified — require_role(admin) |
| `observal-server/api/routes/otel_dashboard.py` | Modified — require_role(admin) |
| `observal-server/api/routes/dashboard.py` | Modified — require_role(admin) |
| `observal-server/api/routes/agent.py` | Modified — require_role(user) |
| `observal-server/api/routes/skill.py` | Modified — require_role(user) |
| `observal-server/api/routes/hook.py` | Modified — require_role(user) |
| `observal-server/api/routes/prompt.py` | Modified — require_role(user) |
| `observal-server/api/routes/sandbox.py` | Modified — require_role(user) |
| `observal-server/api/routes/scan.py` | Modified — require_role(user) |
| `observal-server/api/routes/mcp.py` | Modified — require_role(user) |
| `observal-server/api/routes/component_source.py` | Modified — require_role(user) |
| `observal-server/api/routes/feedback.py` | Modified — require_role(user) |
| `observal-server/api/routes/alert.py` | Modified — require_role(user) |
| `observal-server/tests/test_rbac.py` | New — RBAC hierarchy + require_role tests |
| `observal-server/tests/test_config.py` | New — deployment mode config tests |
