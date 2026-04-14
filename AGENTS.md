# AGENTS.md

Internal context for contributors and AI coding agents. Use `README.md` as the public source of truth for API endpoints and CLI usage. Use `SETUP.md` for environment setup. Use `docs/superpowers/specs/2026-04-10-product-vision.md` for the product vision.

## Current state

Observal is an agent-centric registry and observability platform for AI coding agents. Agents are the primary entity, bundling 5 component types: MCP servers, skills, hooks, prompts, and sandboxes. All components have CRUD, CLI commands, admin review, feedback, and telemetry collection. Agents bundle components via a polymorphic junction table (`agent_components`).

All API routes accept either UUID or name for path parameters. Admin review controls public registry visibility only. Submitters can install and use their own items immediately without approval.

The MCP validator supports multiple frameworks: FastMCP, standard MCP SDK (Python), TypeScript SDK (`@modelcontextprotocol/sdk`), and Go SDK (`mcp-go`). There is no framework enforcement - all MCP implementations are accepted.

The web frontend is a Next.js 16 / React 19 app in `web/`. It uses three route groups: `(auth)` for login, `(registry)` for the public-facing agent browser, component library, and agent builder, and `(admin)` for the admin dashboard, traces, eval, review, and user management. The frontend has a custom OKLCH design system with 5 themes (light, dark, midnight, forest, sunset), three typefaces (Archivo for display, Albert Sans for body, JetBrains Mono for code), and a 4pt spacing scale. It uses shadcn/ui components, Recharts for charts, TanStack Query for data fetching, and TanStack Table for sortable/filterable tables. Shared API response types live in `web/src/lib/types.ts`. The GraphQL API at `/api/v1/graphql` is the read layer for telemetry data; REST endpoints serve everything else.

## CLI structure

The CLI is organized into nested command groups:

```
observal
├── pull                     # install complete agent (primary workflow)
├── scan                     # detect and instrument IDE configs
├── use / profile            # swap IDE configs from git-hosted profiles
├── auth                     # init, login, logout, whoami, status
├── config                   # show, set, path, alias, aliases
├── registry                 # component registry parent group
│   ├── mcp                  #   submit, list, show, install, delete
│   ├── skill                #   submit, list, show, install, delete
│   ├── hook                 #   submit, list, show, install, delete
│   ├── prompt               #   submit, list, show, install, render, delete
│   └── sandbox              #   submit, list, show, install, delete
├── agent                    # create, list, show, install, delete, init, add, build, publish
├── ops                      # observability commands
│   ├── overview, metrics, top, traces, spans
│   ├── rate, feedback
│   └── telemetry            #   status, test
├── admin                    # admin commands
│   ├── settings, set, users
│   ├── penalties, penalty-set, weights, weight-set
│   ├── review               #   list, show, approve, reject
│   └── eval                 #   run, scorecards, show, compare, aggregate
├── self                     # upgrade, downgrade
└── doctor                   # diagnose IDE settings compatibility
```

Deprecated root-level aliases exist for backward compatibility (e.g. `observal submit` → `observal registry mcp submit`, `observal upgrade` → `observal self upgrade`). These are hidden from `--help` and print deprecation warnings.

## Commands

```bash
# Docker stack (7 services: api, db, clickhouse, redis, worker, web, otel-collector)
make up                  # start
make down                # stop
make rebuild             # rebuild and restart
make logs                # tail logs

# CLI (installed via uv)
uv tool install --editable .
observal auth login      # auto-creates admin on fresh server, or login
observal auth whoami     # check auth
observal auth status     # server health check

# Linting
make lint                # ruff check
make format              # ruff format + ruff fix
make check               # pre-commit on all files
make hooks               # install pre-commit hooks

# Tests (526 tests across 18 files, run from observal-server/)
make test                # quick
make test-v              # verbose
# or manually:
cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/ -q
```

## Important files

### API Server (`observal-server/`)

- `main.py` : FastAPI app entrypoint; mounts REST routes + GraphQL at `/api/v1/graphql`; middleware stack includes CORS (env-var origins), security headers, request size limit, rate limiting (slowapi), and session management
- `config.py` : pydantic-settings: DATABASE_URL, CLICKHOUSE_URL, REDIS_URL, SECRET_KEY, eval model config, OAuth settings (all default to None/disabled), rate limit settings
- `worker.py` : arq WorkerSettings; background eval jobs consume from Redis queue
- `api/deps.py` : auth dependency (`get_current_user` via X-API-Key header), DB session injection, `resolve_listing` (name-or-UUID resolver used by all routes)
- `api/graphql.py` : Strawberry schema: Query (traces, spans, metrics) + Subscription (traceCreated, spanCreated); DataLoaders for ClickHouse batch queries
- `api/ratelimit.py` : shared slowapi Limiter instance, backed by Redis
- `api/routes/auth.py` : bootstrap (auto-admin, localhost-only), login, whoami, OAuth code exchange, password reset; all endpoints rate-limited via slowapi
- `api/routes/mcp.py` : MCP server CRUD; submit triggers async validation pipeline
- `api/routes/agent.py` : Agent CRUD with goal templates, component linking via agent_components table
- `api/routes/skill.py` : Skill CRUD; install generates SessionStart/End hook config
- `api/routes/hook.py` : Hook CRUD; install generates IDE-specific HTTP hook config
- `api/routes/prompt.py` : Prompt CRUD + `/render` endpoint that emits prompt_render spans
- `api/routes/sandbox.py` : Sandbox CRUD; install generates observal-sandbox-run config
- `api/routes/review.py` : Admin approve/reject workflow (unified across all component types)
- `api/routes/telemetry.py` : `POST /ingest` (batch traces/spans/scores) + legacy `/events` + `POST /hooks` (raw IDE hook JSON)
- `api/routes/dashboard.py` : MCP metrics, agent metrics, overview stats, top items, trends
- `api/routes/feedback.py` : Ratings with dual-write to PostgreSQL + ClickHouse scores table
- `api/routes/eval.py` : Run evals, list scorecards, compare versions, aggregate stats
- `api/routes/admin.py` : Enterprise settings CRUD, user management, role changes, penalty catalog, dimension weights
- `api/routes/alert.py` : Alert rule CRUD (metric threshold alerts with webhook URLs)
- `api/routes/scan.py` : `POST /api/v1/scan` bulk registration from IDE config scans; deduplicates by name

### Models (`observal-server/models/`)

- `user.py` : User with UserRole enum (admin, developer, user); API key is hashed with SHA-256
- `mcp.py` : McpListing, McpValidationResult, McpDownload; ListingStatus enum (shared by all models)
- `agent.py` : Agent, AgentGoalTemplate, AgentGoalSection, AgentStatus enum
- `alert.py` : AlertRule (metric threshold alerts with webhook URLs)
- `skill.py` : SkillListing, SkillDownload
- `hook.py` : HookListing, HookDownload
- `prompt.py` : PromptListing, PromptDownload
- `sandbox.py` : SandboxListing, SandboxDownload
- `submission.py` : Submission (unified pending submissions)
- `eval.py` : EvalRun, Scorecard, ScoreCardDimension; EvalRunStatus enum
- `feedback.py` : Feedback (polymorphic on listing_type across all component types)
- `enterprise_config.py` : Key-value enterprise settings
- `organization.py` : Organization (id, name, slug, created_at, updated_at)
- `component_source.py` : ComponentSource, Git mirror origins for component discovery
- `agent_component.py` : AgentComponent, polymorphic junction table (agent_id, component_type, component_id); NO FK on component_id
- `download.py` : AgentDownloadRecord (deduplicated by user_id + fingerprint), ComponentDownloadRecord (not deduplicated)
- `exporter_config.py` : ExporterConfig, per-org telemetry export settings (grafana, datadog, loki, otel)

### Services (`observal-server/services/`)

- `clickhouse.py` : ClickHouse HTTP client; DDL for 5 tables (2 legacy + 3 new); insert/query helpers with parameterized SQL builder; `INIT_SQL` runs on startup
- `redis.py` : Redis connection, pub/sub (publish/subscribe), eval job queue (enqueue_eval)
- `config_generator.py` : Generates IDE config snippets per MCP; wraps commands with `observal-shim`; handles stdio vs HTTP transport
- `agent_config_generator.py` : Generates bundled agent configs (rules file + MCP configs); injects OBSERVAL_AGENT_ID env var
- `sandbox_config_generator.py` : Wraps sandbox execution with `observal-sandbox-run` entry point
- `skill_config_generator.py` : Emits SessionStart/End hooks for skill activation telemetry
- `hook_config_generator.py` : Generates IDE-specific HTTP hook configs (Claude Code, Kiro, Cursor)
- `mcp_validator.py` : 2-stage validation: clone+inspect (git clone, find entry point, detect framework) + manifest validation. Detects FastMCP, standard MCP SDK (Python), TypeScript SDK, and Go SDK. No framework enforcement.
- `eval_engine.py` : `EvalBackend` ABC; `LLMJudgeBackend` (Bedrock/OpenAI); `FallbackBackend` (deterministic); 6 managed prompt templates
- `eval_service.py` : Orchestrates eval runs: fetch traces, run backend, create scorecards

### Schemas (`observal-server/schemas/`)

- Pydantic request/response models mirroring the API surface
- `telemetry.py` : TraceIngest, SpanIngest, ScoreIngest, IngestBatch, IngestResponse

### CLI (`observal_cli/`)

- `main.py` : Typer app wiring; creates `registry_app` parent group (mcp, skill, hook, prompt, sandbox), registers all command modules, adds deprecated backward-compat aliases
- `cmd_auth.py` : `auth_app` subgroup: login (smart - auto-bootstrap on fresh server, supports --key for API keys, email+password), register, reset-password, init (removed alias), logout, whoami, status. Also `config_app` subgroup: show, set, path, alias, aliases
- `cmd_mcp.py` : `mcp_app` subgroup: submit (with --yes for non-interactive), list (--sort, --limit, --output), show, install (--raw), delete. `register_deprecated_mcp()` adds hidden root-level bare aliases (submit, list, show, install, delete)
- `cmd_agent.py` : `agent_app` subgroup: create (--from-file), list, show, install, delete; authoring: init, add, build, publish
- `cmd_skill.py` : `skill_app` subgroup: submit, list, show, install, delete
- `cmd_hook.py` : `hook_app` subgroup: submit, list, show, install, delete
- `cmd_prompt.py` : `prompt_app` subgroup: submit, list, show, install, render, delete
- `cmd_sandbox.py` : `sandbox_app` subgroup: submit, list, show, install, delete
- `cmd_scan.py` : `observal scan`: auto-detect IDE configs (Cursor, Kiro, VS Code, Claude Code, Gemini CLI), bulk-register MCPs, wrap with observal-shim; `--dry-run`, `--ide`, `--yes` flags
- `cmd_pull.py` : `observal pull`: fetch agent config from server, write IDE files (rules, MCP config, agent files) to disk; `--dry-run`, `--dir` flags; merges MCP configs with existing files
- `cmd_profile.py` : `observal use` + `observal profile`: swap IDE configs from git-hosted profiles; clones/caches profiles, backs up current config, restores via `observal use default`
- `cmd_ops.py` : `ops_app` subgroup: overview, metrics (--watch), top, traces, spans, rate, feedback. Contains `telemetry_app` (status, test). Also `admin_app` subgroup: settings, set, users, penalties, penalty-set, weights, weight-set. Contains `review_app` (list, show, approve, reject) and `eval_app` (run, scorecards, show, compare, aggregate). Also `self_app` subgroup: upgrade, downgrade. `register_deprecated_ops/admin/lifecycle()` add hidden root-level aliases
- `cmd_doctor.py` : `doctor_app`: diagnose IDE settings for Observal compatibility; checks Observal config, server connectivity, IDE configs (Claude Code, Kiro, Cursor, Gemini CLI), env vars, Docker availability, entry points; `--ide` to target specific IDE, `--fix` to show suggested fixes
- `client.py` : httpx wrapper with get/post/put/delete/health; contextual error messages per status code
- `config.py` : ~/.observal/config.json management; alias system (@name -> UUID resolution)
- `render.py` : Shared Rich rendering: status badges, relative timestamps, IDE color tags, star ratings, kv panels, spinners
- `shim.py` : `observal-shim`: transparent stdio JSON-RPC proxy; pairs requests/responses into spans; caches tools/list for schema compliance; buffered async telemetry flush
- `proxy.py` : `observal-proxy`: HTTP reverse proxy reusing ShimState; same telemetry pipeline
- `sandbox_runner.py` : `observal-sandbox-run`: Docker SDK executor; captures stdout/stderr via container.logs(); reports exit code, OOM, container ID

### Docker (`docker/`)

- `docker-compose.yml` : 7 services: api (8000), db (PostgreSQL 16), clickhouse (8123/9000), redis (6379), worker (arq), web (3000), otel-collector (4317/4318)
- `Dockerfile.api` : uv-based Python build
- `Dockerfile.web` : Node 24-alpine, multi-stage build with standalone output

### Tests (`tests/`)

- 526 tests across 18 files; all mock external services (no Docker needed to run)
- `test_clickhouse_phase1.py` : DDL, SQL helpers, insert/query functions
- `test_ingest_phase2.py` : Ingestion schemas, endpoint, partial failure
- `test_shim_phase3.py` : JSON-RPC parsing, schema compliance, ShimState, config gen
- `test_proxy_phase4.py` : Proxy, HTTP transport config
- `test_worker_phase5.py` : Redis, arq, docker-compose validation
- `test_graphql_phase6.py` : Strawberry types, DataLoaders, resolvers
- `test_eval_phase8.py` : Templates, backends, run_eval_on_trace
- `test_phase9_10.py` : Dual-write, CLI commands
- `test_registry_types.py` : Models, schemas, routes, review, feedback, CLI for all 6 types
- `test_telemetry_collection.py` : Sandbox runner, config generators, install route wiring
- `test_schema_redesign.py` : Organization, ComponentSource, AgentComponent, downloads, ExporterConfig, feedback/submission updates
- `test_agent_composition.py` : Agent composition resolver and multi-component support
- `test_pull_and_agent_cli.py` : Pull command and agent CLI commands
- `test_git_mirror.py` : Git mirroring service
- `test_ragas_eval.py` : RAGAS evaluation metrics
- `test_structural_scorer.py` : Rule-based structural scoring
- `test_slm_scorer.py` : LLM-based SLM scoring
- `test_score_aggregator.py` : Score aggregation and composite grading

### Web Frontend (`web/`)

**Design system:** OKLCH color space with 5 themes (light, dark, midnight, forest, sunset). Typography: Archivo (display/headings), Albert Sans (body), JetBrains Mono (code). 4pt base spacing scale. Motion tokens for animations. Defined in `globals.css`.

Three route groups organize the UI by access level:

**`(auth)/`** - Login and initialization
- `login/page.tsx` : Email/name login and first-run admin init

**`(registry)/`** - Public agent browser (requires auth)
- `page.tsx` : Registry home with search, trending agents, top rated
- `agents/page.tsx` : Agent list table with search and filters
- `agents/[id]/page.tsx` : Agent detail with pull command box
- `agents/builder/page.tsx` : Agent builder with two-column layout, component selector tabs, goal template editor, live YAML preview, publish action
- `components/page.tsx` : Tabbed component browser (MCPs, skills, hooks, prompts, sandboxes)
- `components/[id]/page.tsx` : Component detail view

**`(admin)/`** - Admin dashboard (requires admin role)
- `dashboard/page.tsx` : Overview stats, recent agents, latest traces
- `traces/page.tsx` : Trace list with filtering
- `traces/[id]/page.tsx` : Trace detail with resizable span tree + JSON viewer
- `review/page.tsx` : Admin review queue
- `users/page.tsx` : User management
- `settings/page.tsx` : Enterprise settings
- `eval/page.tsx` : Eval overview with agent scores
- `eval/[agentId]/page.tsx` : Eval detail with aggregate chart, dimension radar, penalty accordion

**Shared components:**
- `src/lib/api.ts` : Typed fetch wrapper; all REST + GraphQL calls; auth via localStorage API key
- `src/lib/types.ts` : Shared TypeScript interfaces for all API responses
- `src/hooks/use-api.ts` : TanStack Query hooks for every endpoint (queries + mutations)
- `src/hooks/use-auth.ts` : Auth guard hook (checks API key exists)
- `src/hooks/use-admin-guard.ts` : Admin role check hook
- `src/hooks/use-mobile.ts` : Mobile viewport detection
- `src/components/layouts/auth-guard.tsx` : Auth guard wrapper
- `src/components/layouts/admin-guard.tsx` : Admin guard wrapper
- `src/components/layouts/dashboard-shell.tsx` : Dashboard layout shell
- `src/components/layouts/page-header.tsx` : Page header with breadcrumbs
- `src/components/nav/registry-sidebar.tsx` : Unified sidebar with conditional admin section
- `src/components/nav/command-menu.tsx` : Command palette (Cmd+K)
- `src/components/nav/nav-user.tsx` : User profile menu
- `src/components/shared/skeleton-layouts.tsx` : Reusable skeletons (TableSkeleton, CardSkeleton, DetailSkeleton, ChartSkeleton)
- `src/components/shared/error-state.tsx` : Reusable error display with retry
- `src/components/shared/empty-state.tsx` : Icon + title + description + CTA
- `src/components/dashboard/` : Stat cards, trend charts, bar lists, heatmap, time range select, no-data/error states
- `src/components/traces/` : Trace list, trace detail, span tree with collapsible thread lines
- `src/components/registry/` : Agent card, component card, pull command with IDE selector, install dialog, metrics panel, feedback list, status badge
- `src/components/eval/` : Eval-specific components

### Demo (`demo/`)

- `test_all_types.sh` : Full e2e test: submit, approve, install, and test all component types with real Docker containers and ClickHouse verification
- `mock_mcp.py`, `mock_agent_mcp.py` : Mock MCP servers for local testing
- `run_demo.sh` : Automated demo script

### Enterprise (`ee/`)

The `ee/` directory contains proprietary enterprise features licensed under the Observal Enterprise License (see `ee/LICENSE`). This code is source-available but requires a commercial license for production use. Community contributions are not accepted into this directory.

**Critical constraint:** The open-source core must never import from `ee/`. The dependency is strictly one-way: `ee/` code can import from the open-source core, but not the reverse. The open-source edition must be fully functional without `ee/`.

## Implementation notes

- Two databases: PostgreSQL for relational data (users, MCPs, agents, feedback, eval runs), ClickHouse for time-series telemetry (traces, spans, scores). They are not interchangeable.
- ClickHouse uses ReplacingMergeTree with bloom filter indexes. Queries go through the HTTP interface, not a native driver. The `_query` helper in `clickhouse.py` handles parameterized queries.
- The shim is the core telemetry collection mechanism. It sits between the IDE and the MCP server, completely transparent. It never modifies messages: only observes. Telemetry is fire-and-forget via async POST; if the server is down, spans are silently dropped.
- Config generators automatically wrap MCP commands with `observal-shim` for stdio transport or point to `observal-proxy` for HTTP transport. This is how telemetry collection is opt-in per install.
- The `observal scan` command reads existing IDE config files, bulk-registers found MCP servers via `POST /api/v1/scan`, and rewrites configs to wrap commands with `observal-shim`. It creates timestamped backups before modifying any file. HTTP-transport MCPs are registered but not shimmed (they would need `observal-proxy`).
- GraphQL is the read layer for telemetry data. REST still exists for auth, CRUD, feedback, eval, admin. The GraphQL layer uses DataLoaders to batch ClickHouse queries.
- Redis serves two purposes: pub/sub for GraphQL subscriptions (live trace/span events) and arq job queue for background eval runs.
- The eval engine is pluggable. `LLMJudgeBackend` calls Bedrock or OpenAI-compatible endpoints. `FallbackBackend` returns deterministic scores when no LLM is configured. The 6 managed templates are prompt strings, not code.
- Feedback dual-writes: when a user rates an MCP/agent, it writes to PostgreSQL (for the feedback API) AND ClickHouse scores table (for unified analytics). The ClickHouse write is best-effort.
- Auth is API key based. Keys are SHA-256 hashed before storage. The `X-API-Key` header is checked on every authenticated request via `get_current_user` dependency. User onboarding uses self-registration (`observal auth register`) or SSO. Fresh servers auto-bootstrap an admin account on first `observal auth login` (zero prompts, localhost-only). The `/health` endpoint returns `initialized: bool` so the CLI knows whether to bootstrap or prompt for credentials. All auth endpoints are rate-limited via slowapi (backed by Redis). OAuth uses a one-time auth code exchange pattern: the callback stores credentials in Redis with a 30s TTL and redirects with an opaque code instead of the raw API key.
- Install routes use an owner fallback: try approved first, then allow the submitter to install their own pending/rejected items. This lets `observal scan` work. Items are auto-registered as pending and immediately usable by the submitter.
- The CLI stores config in `~/.observal/config.json`. Aliases are in `~/.observal/aliases.json`. Both are plain JSON. All API path parameters accept UUID or name; the server resolves names via `resolve_listing()` in `deps.py`.
- All CLI list/show commands support `--output table|json|plain`. Use `--output json` for scripting. Use `--raw` on install commands to pipe config directly to files.
- The CLI uses nested Typer subgroups. Deprecated root-level aliases are registered as hidden commands that print deprecation warnings and delegate to the canonical implementation functions (`_impl` pattern). The `register_deprecated_*` functions in each module handle this.
- Ruff is the Python linter and formatter. Line length is 120. Pre-commit hooks enforce it.
- The `B008` ruff rule is suppressed because Typer requires function calls in argument defaults (`typer.Option(...)`, `typer.Argument(...)`).
- The data model is agent-centric. Agents bundle components (MCPs, skills, hooks, prompts, sandboxes) via `agent_components`, a polymorphic junction table with NO foreign key on `component_id` (allows cross-type references). Agent downloads are deduplicated by `(user_id)` and `(fingerprint)` unique constraints; component downloads are not deduplicated. All components support organization ownership via `is_private` + `owner_org_id` fields. Git-based versioning: components require `git_url` + `git_ref` for reproducible installs.
- The web frontend uses OKLCH color space for perceptually uniform theming. 5 themes are defined in `globals.css` using CSS custom properties. Theme switching is handled by `theme-switcher.tsx`. The design system uses a 4pt spacing scale, semantic color tokens (background, foreground, card, border, primary, secondary, accent, destructive, success, warning, info), and motion tokens for animations.
- The web frontend proxies all API calls through Next.js rewrites (`/api/v1/*` -> backend). The backend URL is configured via `NEXT_PUBLIC_API_URL` env var (defaults to `http://localhost:8000`). Auth state (API key, user role) is stored in localStorage. Role-based access is enforced client-side via AuthGuard and AdminGuard components, not Next.js middleware.
