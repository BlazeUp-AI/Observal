# Enterprise Edition

Source-available enterprise features for Observal. Loaded only when `DEPLOYMENT_MODE=enterprise`.

**License:** Separate enterprise license (`ee/LICENSE`). Commercial license required for production. Community contributions NOT accepted into this directory.

**Critical constraint:** Core must NEVER import from `ee/`. Dependency is strictly one-way: `ee/` imports core, never the reverse. The open-source edition must be fully functional without `ee/`.

## How it loads

`observal-server/main.py` calls `register_enterprise(app, settings)` from `ee/__init__.py` which:

1. Validates enterprise config via `config_validator.py`
2. Mounts EE routes (`/api/v1/sso/saml/*`, `/api/v1/scim/*`, `/api/v1/admin/audit-log*`)
3. Adds `EnterpriseGuardMiddleware` (returns 503 on EE routes if config is invalid)
4. Registers audit event bus handlers on `services.events.bus`
5. Stores config issues in `app.state.enterprise_issues`

## Config validation

Five settings checked on startup. If any fail, issues are stored and the guard middleware blocks EE routes with 503.

| Setting | Requirement |
|---------|------------|
| `SECRET_KEY` | Not the default `"change-me-to-a-random-string"` |
| `OAUTH_CLIENT_ID` | Must be set |
| `OAUTH_CLIENT_SECRET` | Must be set |
| `OAUTH_SERVER_METADATA_URL` | Must be set (OIDC discovery) |
| `FRONTEND_URL` | Not localhost or empty |

## Features

### Audit logging (implemented)

Listens to 8 event types on the core event bus (`services/events.py`):
- `UserCreated`, `UserDeleted`
- `LoginSuccess`, `LoginFailure`
- `RoleChanged`, `SettingsChanged`
- `AlertRuleChanged`, `AgentLifecycleEvent`

Each event → row in ClickHouse `audit_log` table with actor info, resource details, HTTP metadata, and freeform detail JSON.

**API endpoints (admin-only):**
- `GET /api/v1/admin/audit-log` — query with filters (actor, action, resource_type, date range), paginated
- `GET /api/v1/admin/audit-log/export` — CSV download (max 10k rows)

### SAML 2.0 SSO (stub — returns 501)

- `POST /api/v1/sso/saml/login` — initiate SAML login
- `POST /api/v1/sso/saml/acs` — Assertion Consumer Service callback
- `GET /api/v1/sso/saml/metadata` — SP metadata

### SCIM 2.0 provisioning (stub — returns 501)

- `GET /api/v1/scim/Users` — list users
- `POST /api/v1/scim/Users` — create user
- `GET /api/v1/scim/Users/{user_id}` — get user
- `PUT /api/v1/scim/Users/{user_id}` — update user
- `DELETE /api/v1/scim/Users/{user_id}` — delete user

### Plugin registry (placeholder)

`ee/plugins/__init__.py` — future home for Grafana, Prometheus, Datadog, and SIEM integrations.

## Directory layout

```
ee/
├── __init__.py                         # register_enterprise() entrypoint
├── LICENSE                             # Enterprise license
├── AGENTS.md                           # This file
├── README.md                           # Public-facing description
├── docs/
│   └── cli.md                          # EE configuration reference
├── observal_server/
│   ├── middleware/
│   │   └── enterprise_guard.py         # 503 guard for misconfigured EE routes
│   ├── routes/
│   │   ├── __init__.py                 # mount_ee_routes() — mounts all EE routers
│   │   ├── audit.py                    # Audit log query + CSV export
│   │   ├── scim.py                     # SCIM 2.0 stubs
│   │   └── sso_saml.py                # SAML 2.0 stubs
│   └── services/
│       ├── audit.py                    # Event bus handlers → ClickHouse audit_log writes
│       └── config_validator.py         # Startup config validation
└── plugins/
    └── __init__.py                     # Future integrations placeholder
```
