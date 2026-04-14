# Enterprise vs Local Deployment Mode Split — Design Spec

**Issue:** #189
**Branch:** `feat/enterprise-deployment-mode`
**Date:** 2026-04-13
**Status:** Approved

---

## Overview

Observal splits into two deployment modes gated by `DEPLOYMENT_MODE` env var:
- **Local** (default): self-hosted, email+password auth, self-registration, basic RBAC
- **Enterprise**: SSO-only auth, SCIM provisioning, IdP role mapping, audit logging, plugin integrations

Core remains Apache-2.0. Enterprise features live in `ee/` under custom commercial license.

---

## Design Decisions

### Gating
- `DEPLOYMENT_MODE` env var: `"local"` (default) | `"enterprise"`
- No license key validation for now (future issue)

### Import Boundary
- `ee/` imports from `observal-server/`, NEVER the reverse
- Single exception: guarded block in `main.py` calls `ee.register_enterprise(app)`
- Enforced by: ruff `TID251` banned-api rule + CI grep check (dual enforcement)

### PR Series (4 PRs)
1. **PR1**: Alembic init + baseline migration + RBAC foundation + config changes + require_role refactor
2. **PR2**: Deployment mode guards + demo accounts + health endpoints + ee/ structure + hook system + main.py integration
3. **PR3**: Frontend — role guard, login page modes, public config endpoint
4. **PR4**: Docker/env + tests + CI import boundary check

---

## Section 1: RBAC Foundation + Alembic

### 4-Tier Role Hierarchy

```
super_admin > admin > reviewer > user
```

| Role | Permissions | Scope |
|------|-------------|-------|
| `super_admin` | Destructive actions (delete orgs, wipe data, reset images), everything below | Platform-wide |
| `admin` | View all traces, manage users, configure settings, everything below | Org-scoped (enterprise), global (local) |
| `reviewer` | Review/approve submitted components, everything below | Org-scoped (enterprise), global (local) |
| `user` | Upload agents/components, pull configs, view own traces | Own resources |

### UserRole Enum Update (`models/user.py`)

```python
class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    admin = "admin"
    reviewer = "reviewer"  # renamed from "developer"
    user = "user"
```

Add `is_demo: bool` column (default `False`) to User model.

### Alembic Initialization

Full Alembic setup from scratch:
1. `alembic init` with async PostgreSQL driver (`asyncpg`)
2. Baseline migration capturing the full current schema (all existing ORM models)
3. Second migration on top:
   - Add `super_admin` to `userrole` enum (`ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'`)
   - Add `reviewer` to `userrole` enum (`ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'reviewer'`)
   - Update existing rows: `developer` -> `reviewer`
   - Add `is_demo` boolean column (server_default `false`, not nullable)
   - Idempotent, safe on databases with existing data

**Note:** PostgreSQL doesn't support removing enum values. Downgrade for enum changes is best-effort — `developer` value remains in the enum type but won't be used.

### require_role Refactor (`api/deps.py`)

`require_role()` becomes hierarchy-aware:
- Accepts a minimum role level
- If route requires `admin`, both `admin` and `super_admin` pass
- Hierarchy order: `super_admin(0) > admin(1) > reviewer(2) > user(3)`
- Add `require_super_admin` shorthand

Replace ALL inline `_require_admin()` calls across every route file:

| Route File | New Guard |
|-----------|-----------|
| `admin.py` | `require_role(UserRole.admin)` |
| `review.py` | `require_role(UserRole.reviewer)` |
| `agent.py` | `require_role(UserRole.user)` for CRUD |
| `telemetry.py` | `require_role(UserRole.admin)` for viewing all traces |
| `eval.py` | `require_role(UserRole.admin)` |
| `otel_dashboard.py` | `require_role(UserRole.admin)` |
| `skill.py` | `require_role(UserRole.user)` |
| `sandbox.py` | `require_role(UserRole.user)` |
| `prompt.py` | `require_role(UserRole.user)` |
| `hook.py` | `require_role(UserRole.user)` |
| `mcp.py` | `require_role(UserRole.user)` |
| `component_source.py` | `require_role(UserRole.user)` |
| `feedback.py` | `require_role(UserRole.user)` |
| `alert.py` | `require_role(UserRole.user)` |
| `dashboard.py` | `require_role(UserRole.admin)` |
| `scan.py` | `require_role(UserRole.user)` |
| Future destructive endpoints | `require_role(UserRole.super_admin)` |

---

## Section 2: Config + Deployment Mode Guards

### Config Additions (`config.py`)

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

### Route Guards

`require_local_mode` dependency:
- Returns 403 `"Disabled in enterprise mode"` for:
  - `POST /auth/bootstrap`
  - `POST /auth/register`
  - `POST /auth/invite` (enterprise uses SCIM for provisioning)
  - `POST /auth/redeem` (no invite codes in enterprise)
- Enterprise users come in via SSO/SCIM only

### Health Endpoints (Two-Tier)

**`GET /health`** (unauthenticated):
```json
{"status": "ok", "initialized": true}
```
- `status`: `"ok"` | `"degraded"` (degraded if enterprise mode has config issues)
- No details exposed publicly
- K8s readiness probes use this

**`GET /admin/diagnostics`** (admin-only):
```json
{
  "deployment_mode": "enterprise",
  "status": "misconfigured",
  "issues": [
    "SECRET_KEY is using default value",
    "OAUTH_CLIENT_ID is not set",
    "FRONTEND_URL is localhost"
  ]
}
```
- Enterprise config validation: SECRET_KEY not default, OAUTH_CLIENT_ID set, FRONTEND_URL not localhost
- Always available (returns `{"deployment_mode": "local", "status": "ok", "issues": []}` in local mode)

### Public Config Endpoint

**`GET /api/v1/config/public`** (unauthenticated):
```json
{"deployment_mode": "local", "sso_enabled": true, "saml_enabled": false}
```
- Frontend reads this to decide which login UI to show

---

## Section 3: Hook System + ee/ Module Structure

### Hook System (`services/hooks.py`)

Core defines named extension points. EE registers handlers during startup. Core fires them at natural points without knowing who's listening.

```python
class HookRegistry:
    def register(self, event: str, handler: Callable): ...
    async def fire(self, event: str, **kwargs): ...
```

**Named hooks:**

| Hook | Fired When | Kwargs |
|------|-----------|--------|
| `user_created` | After any user creation (register, SSO, SCIM, admin create) | `user`, `db` |
| `user_deleted` | After user deletion | `user`, `db` |
| `login_success` | After successful authentication | `user`, `method` |
| `login_failure` | After failed authentication attempt | `email`, `method`, `reason` |
| `role_changed` | After a user's role is updated | `user`, `old_role`, `new_role` |
| `settings_changed` | After enterprise config key is updated | `key`, `value` |

**Properties:**
- Handlers are async
- Fire is non-blocking: errors are logged, never crash core
- Registry is a singleton on `app.state.hooks`
- EE registers handlers during `register_enterprise()` call

### ee/ Directory Structure

```
ee/
  LICENSE                              (exists, keep as-is)
  __init__.py                          (register_enterprise, register_plugin)
  observal_server/
    __init__.py
    routes/
      __init__.py
      sso_saml.py                      (placeholder -> 501 "Not yet implemented")
      scim.py                          (placeholder -> 501 "Not yet implemented")
    services/
      __init__.py
      sso_provider.py                  (placeholder)
      enterprise_config_validator.py   (config validation logic)
    middleware/
      __init__.py
      enterprise_guard.py              (503 for misconfigured EE routes)
  plugins/
    __init__.py                        (plugin registry)
    grafana/                           (placeholder)
    prometheus/                        (placeholder)
    datadog/                           (placeholder)
    siem/                              (placeholder)
```

### Enterprise Registration Flow

1. `main.py` calls `register_enterprise(app, settings)` if `DEPLOYMENT_MODE == "enterprise"`
2. EE validates config, returns issues list
3. EE mounts routes (SAML, SCIM — all return 501 for now)
4. EE adds `EnterpriseGuardMiddleware` (returns 503 on EE routes when misconfigured)
5. EE registers hook handlers (audit logging placeholders)
6. Issues stored on `app.state.enterprise_issues` for diagnostics endpoint

### Import Boundary Enforcement (Dual)

**Ruff `TID251`** (`pyproject.toml`):
```toml
[tool.ruff.lint]
select = [..., "TID251"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"ee" = { msg = "Core must not import from ee/. Only allowed in main.py." }

[tool.ruff.lint.per-file-ignores]
"observal-server/main.py" = ["TID251"]
```

**CI grep** (`.github/workflows/ci.yml`):
```bash
! grep -rn "from ee\|import ee" observal-server/ --include="*.py" | grep -v "main.py"
```
Required status check — fails the build on any violation.

---

## Section 4: Demo Account Seeding + Cleanup

### Seeding (in `main.py` lifespan)

After DB table creation:
1. Query for any non-demo users (`is_demo = False`)
2. If none exist AND `DEMO_*_EMAIL` env vars are set, create up to 4 demo accounts with `is_demo=True`
3. Log warning: `"Demo accounts active -- create a real super_admin to remove them"`
4. Fire `user_created` hook for each demo account

### Cleanup (`services/demo.py`)

Service function `check_demo_cleanup(db, new_user)` called explicitly from every user-creation codepath:
- `POST /auth/register`
- `POST /auth/bootstrap`
- SSO auto-create (OAuth callback)
- Admin user creation
- Future: SCIM provisioning

**Logic:**
- New non-demo `super_admin` created -> delete ALL demo accounts
- New non-demo `admin` created -> delete demo admin
- New non-demo `reviewer` created -> delete demo reviewer
- New non-demo `user` created -> delete demo user

**Properties:**
- Runs in the same DB transaction as user creation (rollback-safe)
- Fires `user_deleted` hook for each removed demo account
- Logs each deletion: `"Demo <role> account removed -- real <role> created"`

---

## Section 5: Frontend Updates

### Role Guard Refactor

`use-admin-guard.ts` -> `use-role-guard.ts`:

```typescript
type Role = "super_admin" | "admin" | "reviewer" | "user";
const ROLE_HIERARCHY: Role[] = ["super_admin", "admin", "reviewer", "user"];

function useRoleGuard(minRole: Role): { ready: boolean }
```

Hierarchy check: if `minRole` is `reviewer`, then `reviewer`, `admin`, and `super_admin` all pass.

**Display label mapping:**
```typescript
const ROLE_LABELS: Record<Role, string> = {
  super_admin: "Super Admin",
  admin: "Admin",
  reviewer: "Reviewer",
  user: "Viewer",
};
```

Backend enum values are canonical. Frontend uses display labels in all user-facing UI.

### Generic RoleGuard Component

Replaces `AdminGuard`:
```tsx
<RoleGuard minRole="admin">{children}</RoleGuard>
```

### Route Protection

| Route Group | Guard |
|------------|-------|
| `(admin)/layout.tsx` | `RoleGuard minRole="admin"` |
| Review pages | `RoleGuard minRole="reviewer"` |
| Registry pages | `AuthGuard` (any authenticated user) |

### Sidebar

Filter nav items by role hierarchy instead of binary `isAdmin` check:
- Admin section: visible to `admin` + `super_admin`
- Review section: visible to `reviewer` and above
- Registry items: based on `requiresAuth` flag (unchanged)

### Login Page (Deployment Mode Aware)

On mount, fetches `GET /api/v1/config/public`:

**Local mode:**
- Email + password login form
- Registration link
- OIDC button (if `sso_enabled`)
- API key mode
- Password reset

**Enterprise mode:**
- SSO login button only (OIDC + SAML)
- No registration link
- No password form
- Clean, single-action login

### Users Page

- `ROLES` constant updated to 4-tier
- Role dropdown uses display labels
- Role assignment capped at own level:
  - `super_admin` can assign any role
  - `admin` can assign `reviewer` and `user` only
  - `reviewer` and `user` cannot assign roles

---

## Section 6: Docker, Env, Tests, CI

### Docker (`docker-compose.yml`)

Add to API service:
```yaml
DEPLOYMENT_MODE: ${DEPLOYMENT_MODE:-local}
DEMO_SUPER_ADMIN_EMAIL: ${DEMO_SUPER_ADMIN_EMAIL:-super@demo.example}
DEMO_SUPER_ADMIN_PASSWORD: ${DEMO_SUPER_ADMIN_PASSWORD:-super-changeme}
DEMO_ADMIN_EMAIL: ${DEMO_ADMIN_EMAIL:-admin@demo.example}
DEMO_ADMIN_PASSWORD: ${DEMO_ADMIN_PASSWORD:-admin-changeme}
DEMO_REVIEWER_EMAIL: ${DEMO_REVIEWER_EMAIL:-reviewer@demo.example}
DEMO_REVIEWER_PASSWORD: ${DEMO_REVIEWER_PASSWORD:-reviewer-changeme}
DEMO_USER_EMAIL: ${DEMO_USER_EMAIL:-user@demo.example}
DEMO_USER_PASSWORD: ${DEMO_USER_PASSWORD:-user-changeme}
```

### `.env.example`

Add all new vars under clear section headers with comments.

### CI Import Boundary (`.github/workflows/ci.yml`)

New `import-boundary` job:
```bash
! grep -rn "from ee\|import ee" observal-server/ --include="*.py" | grep -v "main.py"
```
Required status check.

### Ruff Config (`pyproject.toml`)

Add `TID251` to selected rules. Configure `banned-api` for `ee` module. Per-file-ignore exempting `main.py`.

### Tests

| Test | Validates |
|------|----------|
| 4-tier RBAC | Each role can only access its permitted endpoints |
| Role hierarchy | `super_admin` passes `admin` checks, `admin` passes `reviewer` checks |
| `require_local_mode` | Bootstrap/register return 403 in enterprise mode |
| Demo seeding | Accounts created when env vars set + no real users |
| Demo cleanup | Cascading deletion when real `super_admin` created; per-tier for lower roles |
| Health endpoint | `/health` returns `degraded` (no details) in misconfigured enterprise |
| Admin diagnostics | `/admin/diagnostics` returns full issues behind auth |
| EE route 501 | SAML/SCIM placeholders return 501 |
| EE route 503 | Misconfigured enterprise returns 503 on EE routes |
| Hook system | Handlers registered, fired on events, errors don't crash core |
| Alembic migration | `developer` -> `reviewer` rename on existing data, `super_admin` added, `is_demo` column |
| Public config | Returns correct `deployment_mode` and SSO flags |
| Role assignment cap | Admin can't assign `admin` or `super_admin` roles |

---

## Future: Agent Registry Access Control

**Not in scope for this work.** Documented here for architectural alignment.

The Agent Registry will use a **Backstage/Artifactory catalog model** for visibility and access control:

### Visibility Tiers (per agent/component)
- `public` — visible to anyone, including unauthenticated users
- `internal` — visible to any authenticated user on the platform
- `org` — visible only to members of the owning organization
- `private` — visible only to the owner and explicitly granted users/teams

### Access Grants
On top of visibility tiers, explicit grants enable cross-org sharing:
- Org X grants Org Y read access to agent Z
- Team "platform-eng" gets access to all agents tagged "infrastructure"
- Individual user gets access to a specific private agent

### Catalog Layer
Separation between **Registry** (where agents are stored, visibility-controlled) and **Catalog** (curated view filtered by user's org membership, role, and grants). Query layer filters results based on requesting user's context.

### RBAC Integration
The 4-tier role hierarchy handles coarse authorization (who can publish, approve, manage). A future fine-grained permission layer (Grafana hybrid model) adds action-scope permissions:
- `agents:publish` — submit an agent to the registry
- `agents:approve` — approve/reject submitted agents
- `agents:fork` — fork an agent into your org
- `agents:delete` — remove from registry
- `agents:read` — view agent details
- `catalog:read` — browse shared catalog
- `catalog:manage` — curate catalog visibility

Roles provide permission defaults; individual overrides per-user or per-org in enterprise mode.

---

## Feature Split Summary

| Core (local mode) | ee/ (enterprise mode) |
|--------------------|-----------------------|
| Email + password auth | SAML 2.0 SSO |
| Basic OIDC (authlib) | SCIM 2.0 provisioning |
| Bootstrap endpoint | Multi-IdP config (per-org) |
| Self-registration | Azure AD / Okta adapters |
| Account creation page | IdP group -> role mapping |
| 4-tier basic RBAC | Audit logging |
| Invite codes | SIEM integration (plugin) |
| JWT tokens (HS256/ES256) | GDPR tools |
| Password reset | Encryption at rest |
| API key auth | Secrets manager integration (plugin) |
| Hook system (core) | Hook handlers (ee/) |
| Public config endpoint | Enterprise config validation |
| | Team access control |
| | Multi-tenancy enforcement |
| | Grafana/Prometheus/Datadog exporters (plugins) |

---

## Constraints

- All Alembic migrations in `observal-server/alembic/versions/` (NEVER in ee/)
- Import boundary: ee/ imports core, never reverse. Only exception: main.py
- All git commits use `-s` flag (DCO sign-off)
- Rebase on upstream/main before pushing
- SAML/SCIM/audit internals are placeholders only (501 responses)
- Don't touch multi-tenancy (#196) — org-scoping is a separate issue
- Rename `developer` role to `reviewer` in this PR series
