# Context Handoff: Registry Expansion

**Date:** 2026-04-04
**Branch:** `feature/registry-expansion`
**Tests:** 261 passing (181 original + 80 new)

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

### Docs
- `docs/design-new-registry-types.md` - full design spec (models, APIs, CLI, validation, telemetry, implementation order)
- `docs/telemetry-collection-architecture.md` - how each type collects telemetry (no wrapper binaries)

## What's left to implement

### 1. Sandbox exec runner (`observal_cli/sandbox_runner.py`)
- Python entry point `observal-sandbox-run` that:
  - Runs `docker run` via Docker Python SDK (`docker.from_env().containers.run()`)
  - Streams and captures stdout/stderr (these ARE the command logs)
  - After container exits: calls `container.stats(stream=False)` for cgroup metrics
  - Reads: CPU usage from `cpu_stats`, memory from `memory_stats.usage`/`limit`, network from `networks`, block I/O from `blkio_stats`
  - Checks `State.OOMKilled` for OOM detection
  - Gets exit code from `container.wait()`
  - POSTs a `sandbox_exec` span to `/api/v1/telemetry/ingest` with all metrics + logs
- Register as entry point in `pyproject.toml` alongside `observal-shim` and `observal-proxy`
- Docker SDK (`docker` package) needs to be added to dependencies
- Container logs (stdout/stderr) go into the span's `output` field (truncated to 10KB)

### 2. GraphRAG proxy (`observal_cli/graphrag_proxy.py`)
- HTTP reverse proxy (like `observal-proxy`) between agent and GraphRAG endpoint
- Intercepts HTTP requests to the GraphRAG endpoint_url
- For each request/response pair, creates a `retrieval` span with:
  - query_interface (detect from content-type or path)
  - latency_ms
  - input (query), output (response, truncated)
  - Parse response to extract entity/relationship counts if possible
- Reuse `ShimState` pattern from proxy.py for buffered async telemetry flush
- Register as entry point `observal-graphrag-proxy` in pyproject.toml

### 3. Config generators for remaining types
- `services/tool_config_generator.py`: for HTTP tools, wrap endpoint_url with observal-proxy; for non-HTTP, emit PostToolUse hook
- `services/skill_config_generator.py`: emit SessionStart hook that reports loaded skills, Stop hook that reports deactivation
- `services/sandbox_config_generator.py`: wrap docker run command with observal-sandbox-run
- `services/graphrag_config_generator.py`: point agent at observal-graphrag-proxy URL instead of direct endpoint
- Update each type's install route to call its config generator instead of returning generic snippet

### 4. Tests for telemetry code
- Test hook ingest endpoint (POST /api/v1/telemetry/hooks with mock hook JSON)
- Test prompt render span emission (mock insert_spans, verify it's called)
- Test ClickHouse schema extensions (verify ALTER TABLE statements in INIT_SQL)
- Test new SpanIngest/TraceIngest fields validate correctly
- Test hook_config_generator output for each IDE
- Test sandbox_runner (mock docker SDK)
- Test graphrag_proxy (mock HTTP target)

### 5. GraphQL extensions
- New query types: ToolMetrics, SandboxMetrics, GraphRagMetrics, HookMetrics, SkillMetrics, PromptMetrics
- Extend Span strawberry type with new fields
- Add subscription filters by trace_type and span type
- Update overview stats to count all 8 registry types

### 6. Dashboard metrics routes
- `GET /api/v1/{type}/{id}/metrics` for each new type
- Query ClickHouse for type-specific aggregates (latency percentiles, error rates, etc.)
- Sandbox: CPU/memory/OOM/timeout rates
- GraphRAG: relevance scores, entity counts, embedding latency
- Hooks: execution count per event, block rate
- Prompts: render count, token expansion ratio

### 7. Skill route bug
- `api/routes/skill.py` submit endpoint was passing `archive_url` to SkillListing but model doesn't have that column
- Fixed in route but `schemas/skill.py` still has `archive_url` field in SubmitRequest - should remove or add column to model

## Key files to read first
- `docs/telemetry-collection-architecture.md` - how telemetry works per type
- `docs/design-new-registry-types.md` - full design spec
- `observal_cli/shim.py` - existing telemetry proxy pattern to replicate
- `observal_cli/proxy.py` - existing HTTP proxy pattern to replicate
- `observal-server/services/clickhouse.py` - ClickHouse insert helpers
- `observal-server/api/routes/telemetry.py` - ingest endpoint

## Docker SDK container.stats() reference
`container.stats(stream=False)` returns a dict with:
- `cpu_stats.cpu_usage.total_usage` (nanoseconds)
- `memory_stats.usage` (bytes), `memory_stats.limit` (bytes)
- `networks.eth0.rx_bytes`, `networks.eth0.tx_bytes`
- `blkio_stats.io_service_bytes_recursive` (list of {op, value})
- Container logs via `container.logs(stdout=True, stderr=True)`
- Exit code via `container.wait()['StatusCode']`
- OOM via `container.attrs['State']['OOMKilled']`
