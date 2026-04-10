# AGENTS.md

Internal context for contributors and AI coding agents. Use `README.md` as the public source of truth for API endpoints and CLI usage. Use `SETUP.md` for environment setup. Use `docs/submission-and-install-guide.md` for the submission and install workflow.

## Current state

Observal is an agent-centric registry and observability platform for AI coding agents. Agents are the primary entity, bundling 5 component types: MCP servers, skills, hooks, prompts, and sandboxes. All components have CRUD, CLI commands, admin review, feedback, and telemetry collection. Agents bundle components via a polymorphic junction table (`agent_components`).

All API routes accept either UUID or name for path parameters. Admin review controls public registry visibility only — submitters can install and use their own items immediately without approval.

The web frontend is a Next.js 16 / React 19 app in `web/`. It uses shadcn/ui components, Recharts for charts, TanStack Query for data fetching, and TanStack Table for sortable/filterable tables. Shared API response types live in `web/src/lib/types.ts`. The GraphQL API at `/api/v1/graphql` is the read layer for telemetry data; REST endpoints serve everything else.

## Commands

```bash
# Docker stack (5 containers: api, db, clickhouse, redis, worker)
make up                  # start
make down                # stop
make rebuild             # rebuild and restart
make logs                # tail logs

# CLI (installed via uv)
uv tool install --editable .
observal init            # first-run admin setup
observal whoami          # check auth
observal status          # server health check

# Linting
make lint                # ruff check
make format              # ruff format + ruff fix
make check               # pre-commit on all files
make hooks               # install pre-commit hooks

# Tests (377 unit tests, run from observal-server/)
make test                # quick
make test-v              # verbose
# or manually:
cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with docker pytest ../tests/ -q
```

## Important files

### API Server (`observal-server/`)

- `main.py` : FastAPI app entrypoint; mounts REST routes + GraphQL at `/api/v1/graphql`
- `config.py` : pydantic-settings: DATABASE_URL, CLICKHOUSE_URL, REDIS_URL, SECRET_KEY, eval model config
- `worker.py` : arq WorkerSettings; background eval jobs consume from Redis queue
- `api/deps.py` : auth dependency (`get_current_user` via X-API-Key header), DB session injection, `resolve_listing` (name-or-UUID resolver used by all routes)
- `api/graphql.py` : Strawberry schema: Query (traces, spans, metrics) + Subscription (traceCreated, spanCreated); DataLoaders for ClickHouse batch queries
- `api/routes/auth.py` : init, login, whoami
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
- `api/routes/eval.py` : Run evals, list scorecards, compare versions
- `api/routes/admin.py` : Enterprise settings CRUD, user management, role changes
- `api/routes/alert.py` : Alert rule CRUD (metric threshold alerts with webhook URLs)
- `api/routes/scan.py` : `POST /api/v1/scan` bulk registration from IDE config scans; deduplicates by name

### Models (`observal-server/models/`)

- `user.py` : User with UserRole enum (admin, developer, user); API key is hashed with SECRET_KEY
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
- `component_source.py` : ComponentSource — Git mirror origins for component discovery
- `agent_component.py` : AgentComponent — polymorphic junction table (agent_id, component_type, component_id); NO FK on component_id
- `download.py` : AgentDownloadRecord (deduplicated by user_id + fingerprint), ComponentDownloadRecord (not deduplicated)
- `exporter_config.py` : ExporterConfig — per-org telemetry export settings (grafana, datadog, loki, otel)

### Services (`observal-server/services/`)

- `clickhouse.py` : ClickHouse HTTP client; DDL for 5 tables (2 legacy + 3 new); insert/query helpers with parameterized SQL builder; `INIT_SQL` runs on startup
- `redis.py` : Redis connection, pub/sub (publish/subscribe), eval job queue (enqueue_eval)
- `config_generator.py` : Generates IDE config snippets per MCP; wraps commands with `observal-shim`; handles stdio vs HTTP transport
- `agent_config_generator.py` : Generates bundled agent configs (rules file + MCP configs); injects OBSERVAL_AGENT_ID env var
- `sandbox_config_generator.py` : Wraps sandbox execution with `observal-sandbox-run` entry point
- `skill_config_generator.py` : Emits SessionStart/End hooks for skill activation telemetry
- `hook_config_generator.py` : Generates IDE-specific HTTP hook configs (Claude Code, Kiro, Cursor)
- `mcp_validator.py` : 2-stage validation: clone+inspect (git clone, find entry point, parse AST for FastMCP tools) + manifest validation
- `eval_engine.py` : `EvalBackend` ABC; `LLMJudgeBackend` (Bedrock/OpenAI); `FallbackBackend` (deterministic); 6 managed prompt templates
- `eval_service.py` : Orchestrates eval runs: fetch traces, run backend, create scorecards

### Schemas (`observal-server/schemas/`)

- Pydantic request/response models mirroring the API surface
- `telemetry.py` : TraceIngest, SpanIngest, ScoreIngest, IngestBatch, IngestResponse

### CLI (`observal_cli/`)

- `main.py` : Typer app wiring; imports and registers all command modules
- `cmd_auth.py` : init, login, logout, whoami, status, version; `config` subcommand (show, set, path, alias, aliases)
- `cmd_mcp.py` : submit (with --yes for non-interactive), list (--sort, --limit, --output), show, install (--raw), delete
- `cmd_agent.py` : create (--from-file), list, show, install, delete; new: pull, init, add, build, test, publish
- `cmd_skill.py` : submit, list, show, install, delete
- `cmd_hook.py` : submit, list, show, install, delete
- `cmd_prompt.py` : submit, list, show, install, render, delete
- `cmd_sandbox.py` : submit, list, show, install, delete
- `cmd_scan.py` : `observal scan`: auto-detect IDE configs (Cursor, Kiro, VS Code, Windsurf, Claude Code, Gemini CLI), bulk-register MCPs, wrap with observal-shim; `--dry-run`, `--ide`, `--yes` flags
- `cmd_ops.py` : review, telemetry, dashboard (overview, metrics --watch, top), feedback, eval (run, scorecards, show, compare), admin, traces, spans, upgrade/downgrade
- `client.py` : httpx wrapper with get/post/put/delete/health; contextual error messages per status code
- `config.py` : ~/.observal/config.json management; alias system (@name -> UUID resolution)
- `render.py` : Shared Rich rendering: status badges, relative timestamps, IDE color tags, star ratings, kv panels, spinners
- `shim.py` : `observal-shim`: transparent stdio JSON-RPC proxy; pairs requests/responses into spans; caches tools/list for schema compliance; buffered async telemetry flush
- `proxy.py` : `observal-proxy`: HTTP reverse proxy reusing ShimState; same telemetry pipeline
- `sandbox_runner.py` : `observal-sandbox-run`: Docker SDK executor; captures stdout/stderr via container.logs(); reports exit code, OOM, container ID

### Docker (`docker/`)

- `docker-compose.yml` : 5 services: api (8000), db (PostgreSQL 16), clickhouse (8123/9000), redis (6379), worker (arq)
- `Dockerfile.api` : uv-based Python build

### Tests (`tests/`)

- 377 unit tests; all mock external services (no Docker needed to run)
- `test_clickhouse_phase1.py` : DDL, SQL helpers, insert/query functions (43 tests)
- `test_ingest_phase2.py` : Ingestion schemas, endpoint, partial failure (15 tests)
- `test_shim_phase3.py` : JSON-RPC parsing, schema compliance, ShimState, config gen (43 tests)
- `test_proxy_phase4.py` : Proxy, HTTP transport config (13 tests)
- `test_worker_phase5.py` : Redis, arq, docker-compose validation (16 tests)
- `test_graphql_phase6.py` : Strawberry types, DataLoaders, resolvers (27 tests)
- `test_eval_phase8.py` : Templates, backends, run_eval_on_trace (17 tests)
- `test_phase9_10.py` : Dual-write, CLI commands (7 tests)
- `test_registry_types.py` : Models, schemas, routes, review, feedback, CLI for all 6 new types (72 tests)
- `test_telemetry_collection.py` : Sandbox runner, config generators, install route wiring (20 tests)
- `test_schema_redesign.py` : Organization, ComponentSource, AgentComponent, downloads, ExporterConfig, feedback/submission updates (56 tests)
- `conftest.py` : Adds observal-server to sys.path so tests can import server modules

### Web Frontend (`web/`)

- `src/lib/api.ts` : Typed fetch wrapper; all REST + GraphQL calls; auth via localStorage API key
- `src/lib/types.ts` : Shared TypeScript interfaces for all API responses
- `src/hooks/use-api.ts` : TanStack Query hooks for every endpoint (queries + mutations)
- `src/app/(dashboard)/page.tsx` : Dashboard home with stat cards, trends, heatmap, quick nav
- `src/app/(dashboard)/layout.tsx` : Sidebar + auth guard + command menu + toaster
- `src/components/nav/app-sidebar.tsx` : Navigation sidebar with all registry/observability/eval sections
- `src/components/traces/` : Trace list, trace detail (resizable span tree + JSON viewer), span tree with collapsible thread lines
- `src/components/live/trace-stream.tsx` : Real-time trace stream with pause/resume and server-side filtering
- `src/components/registry/` : Generic registry table (TanStack Table), detail view, install dialog, metrics panel
- `src/components/dashboard/` : Reusable stat cards, trend charts, bar lists, heatmap, time range select, no-data/error states

### Demo (`demo/`)

- `test_all_types.sh` : Full e2e test: submit, approve, install, and test all component types with real Docker containers and ClickHouse verification
- `mock_mcp.py`, `mock_agent_mcp.py` : Mock MCP servers for local testing
- `run_demo.sh` : Automated demo script

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
- Auth is API key based. Keys are hashed with SECRET_KEY before storage. The `X-API-Key` header is checked on every authenticated request via `get_current_user` dependency.
- Install routes use an owner fallback: try approved first, then allow the submitter to install their own pending/rejected items. This lets `observal scan` work — items are auto-registered as pending and immediately usable by the submitter.
- The CLI stores config in `~/.observal/config.json`. Aliases are in `~/.observal/aliases.json`. Both are plain JSON. All API path parameters accept UUID or name; the server resolves names via `resolve_listing()` in `deps.py`.
- All CLI list/show commands support `--output table|json|plain`. Use `--output json` for scripting. Use `--raw` on install commands to pipe config directly to files.
- Ruff is the Python linter and formatter. Line length is 120. Pre-commit hooks enforce it.
- The `B008` ruff rule is suppressed because Typer requires function calls in argument defaults (`typer.Option(...)`, `typer.Argument(...)`).
- The data model is agent-centric. Agents bundle components (MCPs, skills, hooks, prompts, sandboxes) via `agent_components`, a polymorphic junction table with NO foreign key on `component_id` (allows cross-type references). Agent downloads are deduplicated by `(user_id)` and `(fingerprint)` unique constraints; component downloads are not deduplicated. All components support organization ownership via `is_private` + `owner_org_id` fields. Git-based versioning: components require `git_url` + `git_ref` for reproducible installs.
