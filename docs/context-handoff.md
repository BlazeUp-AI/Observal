# Context Handoff: Registry Expansion

**Date:** 2026-04-04
**Branch:** `feature/registry-expansion`
**Tests:** 293 passing (261 original + 32 new)

## What's done

### Registry CRUD (all 6 new types fully wired)
- Models: `models/{tool,skill,hook,prompt,sandbox,graphrag,submission}.py` + downloads + link tables
- Schemas: `schemas/{tool,skill,hook,prompt,sandbox,graphrag}.py` + feedback extended to 8 types
- Routes: `api/routes/{tool,skill,hook,prompt,sandbox,graphrag}.py` - full CRUD (submit/list/show/install/delete)
- CLI: `observal_cli/cmd_{tool,skill,hook,prompt,sandbox,graphrag}.py` - all commands
- `main.py` wires all 6 new routers. CLI `main.py` registers all 6 command groups
- Unified review in `api/routes/review.py` queries all listing types via LISTING_MODELS dict
- Tests in `tests/test_registry_types.py` - 80 tests covering models, schemas, routes, review, feedback, CLI

### Telemetry pipeline extensions
- ClickHouse: 18 new span columns (sandbox, graphrag, hook, prompt fields) + 6 new trace columns
- `schemas/telemetry.py`: TraceIngest + SpanIngest extended with all new fields
- `api/routes/telemetry.py`: ingest route maps new fields, new `POST /api/v1/telemetry/hooks` endpoint accepts raw IDE hook JSON
- `api/routes/prompt.py`: `/render` endpoint emits `prompt_render` spans to ClickHouse (fire-and-forget)
- `services/hook_config_generator.py`: generates IDE-specific HTTP hook configs (Claude Code, Kiro, Cursor)
- Hook install route returns real telemetry config instead of generic snippet

### Real telemetry collection (NEW)
- `observal_cli/sandbox_runner.py`: Docker sandbox executor using `container.logs(stdout=True, stderr=True)` for real stdout/stderr capture, exit code, OOM detection, span emission to ClickHouse
- `observal_cli/graphrag_proxy.py`: HTTP reverse proxy for GraphRAG endpoints, captures query/response pairs as `retrieval` spans with query interface detection (graphql/sparql/cypher/rest)
- `services/sandbox_config_generator.py`: wraps sandbox execution with `observal-sandbox-run`
- `services/graphrag_config_generator.py`: routes GraphRAG traffic through `observal-graphrag-proxy`
- `services/tool_config_generator.py`: HTTP tools use `observal-proxy`, non-HTTP tools emit PostToolUse hooks
- `services/skill_config_generator.py`: emits SessionStart/End hooks for skill activation telemetry
- All install routes now call their config generators instead of returning `{"name": "..."}` stubs
- Prompt install returns real config with render URL
- Entry points `observal-sandbox-run` and `observal-graphrag-proxy` registered in `pyproject.toml`
- `docker` package added to dependencies
- 32 new tests in `tests/test_telemetry_collection.py`
- Integration tested with real Docker containers (alpine, python:3.12-slim)
- Spec doc: `docs/telemetry-log-collection-spec.md`

### Docs
- `docs/design-new-registry-types.md` - full design spec (models, APIs, CLI, validation, telemetry, implementation order)
- `docs/telemetry-collection-architecture.md` - how each type collects telemetry (no wrapper binaries)
- `docs/telemetry-log-collection-spec.md` - implementation spec for real log collection per type

## What's left to implement

### 1. GraphQL extensions
- New query types: ToolMetrics, SandboxMetrics, GraphRagMetrics, HookMetrics, SkillMetrics, PromptMetrics
- Extend Span strawberry type with new fields
- Add subscription filters by trace_type and span type
- Update overview stats to count all 8 registry types

### 2. Dashboard metrics routes
- `GET /api/v1/{type}/{id}/metrics` for each new type
- Query ClickHouse for type-specific aggregates (latency percentiles, error rates, etc.)
- Sandbox: CPU/memory/OOM/timeout rates
- GraphRAG: relevance scores, entity counts, embedding latency
- Hooks: execution count per event, block rate
- Prompts: render count, token expansion ratio

### 3. Skill route bug
- `api/routes/skill.py` submit endpoint was passing `archive_url` to SkillListing but model doesn't have that column
- Fixed in route but `schemas/skill.py` still has `archive_url` field in SubmitRequest - should remove or add column to model

## Key files to read first
- `docs/telemetry-log-collection-spec.md` - how each type captures real logs
- `docs/telemetry-collection-architecture.md` - collection mechanisms overview
- `observal_cli/sandbox_runner.py` - Docker SDK based sandbox executor
- `observal_cli/graphrag_proxy.py` - GraphRAG HTTP reverse proxy
- `observal-server/services/*_config_generator.py` - config generators for each type
- `observal-server/api/routes/telemetry.py` - ingest endpoint
