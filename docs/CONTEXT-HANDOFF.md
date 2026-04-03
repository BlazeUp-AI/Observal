# Context Handoff — Observal Overhaul (Session 2)

> Complete context dump for continuing work. Delete after use.

## What Was Done This Session

Started from the original CONTEXT-HANDOFF.md. Completed Phases 1–10 + Phase 13, plus demo framework, Docker stack fixes, and end-to-end testing.

## Current State

- **Git branch**: `fixups`
- **Git remote**: origin = `Haz3-jolt/Observal`, upstream = `BlazeUp-AI/Observal`
- **GitHub Issues**: #10–#24 (all 15 phases) created on `BlazeUp-AI/Observal`
- **Docker stack**: Running (6 containers: API, web, DB, ClickHouse, Redis, worker)
- **CLI installed**: `observal`, `observal-shim`, `observal-proxy`, `observal-tui` (4 executables)
- **Tests**: 181 passing (run from `observal-server/` with `uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with textual pytest ../tests/ -q`)
- **API key**: `b950f7fc1c690ebabd449f2686846f6b8d1f51aff94a67feca4d605dd867694e` (admin@test.com)
- **Config**: `~/.observal/config.json` has server_url + api_key

## Phase Status

| Phase | Issue | Status | Summary |
|-------|-------|--------|---------|
| 1 — ClickHouse Schema | #10 | ✅ | traces, spans, scores tables with project_id, ReplacingMergeTree, bloom filters |
| 2 — Ingestion Endpoint | #11 | ✅ | POST /api/v1/telemetry/ingest with server-side user_id/environment injection |
| 3 — Shim (stdio) | #12 | ✅ | observal-shim: JSON-RPC parsing, request/response pairing, schema compliance, buffered telemetry |
| 4 — Proxy (HTTP) | #13 | ✅ | observal-proxy: HTTP reverse proxy reusing ShimState |
| 5 — Redis + Worker | #14 | ✅ | Redis 7 container, arq worker, pub/sub service, eval job queue |
| 6 — GraphQL Layer | #15 | ✅ | Strawberry at /api/v1/graphql, DataLoaders, subscriptions, REST dashboard killed |
| 7 — Dashboard Rewrite | #16 | ✅ | Vite + React + urql SPA replacing Next.js |
| 8 — Eval Engine | #17 | ✅ | Pluggable EvalBackend ABC, LLMJudgeBackend, FallbackBackend, 6 managed templates |
| 9 — Score Unification | #18 | ✅ | Feedback dual-writes to PostgreSQL + ClickHouse scores table |
| 10 — CLI Updates | #19 | ✅ | observal upgrade/downgrade/traces/spans commands |
| 11 — Testing & CI | #20 | ❌ | pytest infra exists but no GitHub Actions, no Playwright |
| 12 — Auth / SSO | #21 | ❌ | Deferred per design doc — needs Keycloak, OIDC review |
| 13 — TUI Overhaul | #22 | ✅ | Textual app: Overview, MCPs, Agents, Traces (with span drill-down), Account |
| 14 — ITJ Integration | #23 | ❌ | Future — Information-Theoretic Judge |
| 15 — Release Engineering | #24 | ❌ | Future — compiled binaries, package registries |

## Key Files Created/Modified

### Phase 1-2 (ClickHouse + Ingestion)
- `observal-server/services/clickhouse.py` — INIT_SQL with 5 tables (2 legacy + 3 new), insert_traces/spans/scores, query functions, SQL helpers
- `observal-server/schemas/telemetry.py` — TraceIngest, SpanIngest, ScoreIngest, IngestBatch, IngestResponse
- `observal-server/api/routes/telemetry.py` — POST /ingest route + legacy /events preserved

### Phase 3-4 (Shim + Proxy)
- `observal_cli/shim.py` — ShimState, classify_message, extract_span_type/name, check_schema_compliance, run_shim, main
- `observal_cli/proxy.py` — ProxyState(extends ShimState), _handle_request, run_proxy, main
- `observal-server/services/config_generator.py` — generate_config wraps with observal-shim, proxy_port for HTTP
- `observal-server/services/agent_config_generator.py` — _inject_agent_id for OBSERVAL_AGENT_ID

### Phase 5-6 (Redis + GraphQL)
- `observal-server/services/redis.py` — get_redis, publish, subscribe, enqueue_eval, close
- `observal-server/worker.py` — arq WorkerSettings, run_eval job
- `observal-server/api/graphql.py` — Strawberry schema: Query (traces, trace, span, mcpMetrics, overview, trends) + Subscription (traceCreated, spanCreated), DataLoaders, row converters
- `observal-server/main.py` — GraphQL mounted at /api/v1/graphql, dashboard router removed

### Phase 7 (Dashboard)
- `observal-web/` — Complete Vite + React + urql rewrite (replaced Next.js)
- Components: TraceExplorer, TraceDetail, Overview, McpMetrics
- `observal-web/src/lib/urql.ts` — urql client with WebSocket subscriptions
- `observal-web/src/lib/queries.ts` — GraphQL queries and subscriptions

### Phase 8 (Eval Engine)
- `observal-server/services/eval_engine.py` — EvalBackend ABC, LLMJudgeBackend, FallbackBackend, 6 templates (tool_selection_accuracy, tool_output_utility, reasoning_clarity, response_quality, graph_faithfulness, recall_accuracy), run_eval_on_trace

### Phase 9-10 (Score Unification + CLI)
- `observal-server/api/routes/feedback.py` — Dual-write to PostgreSQL + ClickHouse scores
- `observal_cli/main.py` — Added: tui, upgrade, downgrade, traces, spans commands

### Phase 13 (TUI)
- `observal_cli/tui.py` — Textual app: ObservalTUI with OverviewPanel, McpPanel, AgentPanel, TracePanel, FeedbackPanel, StatCard widget

### Demo Framework
- `demo/mock_mcp.py` — 5 tools (echo, add, read_file, write_file, search)
- `demo/mock_graphrag_mcp.py` — 3 tools (graph_query, graph_traverse, entity_lookup)
- `demo/mock_agent_mcp.py` — 4 tools (delegate_task, reasoning_step, memory_store, memory_retrieve)
- `demo/run_demo.sh` — End-to-end demo script
- `demo/kiro_agent.json` — Kiro agent config with hooks (PreToolUse, PostToolUse, Stop)
- `demo/claude_code_hooks.json` — Claude Code hooks config
- `demo/cursor_mcp.json` — Cursor/VS Code MCP config
- `demo/gemini_cli_mcp.json` — Gemini CLI config

### Tests
- `tests/test_clickhouse_phase1.py` — 43 tests (DDL, helpers, insert, query)
- `tests/test_ingest_phase2.py` — 15 tests (schemas, endpoint, partial failure)
- `tests/test_shim_phase3.py` — 43 tests (JSON-RPC, schema compliance, ShimState, config gen)
- `tests/test_proxy_phase4.py` — 13 tests (proxy, HTTP transport config)
- `tests/test_worker_phase5.py` — 16 tests (Redis, arq, docker-compose)
- `tests/test_graphql_phase6.py` — 27 tests (types, DataLoaders, resolvers, schema)
- `tests/test_eval_phase8.py` — 17 tests (templates, backends, run_eval_on_trace)
- `tests/test_phase9_10.py` — 7 tests (dual-write, CLI commands)

### Docker
- `docker/docker-compose.yml` — 6 services: api, web, db, clickhouse, redis, worker
- `docker/Dockerfile.api` — uv-based Python build
- `docker/Dockerfile.web` — Multi-stage Vite build with serve

### Config
- `.env` — Has REDIS_URL=redis://observal-redis:6379
- `.env.example` — Updated with REDIS_URL
- `pyproject.toml` — 4 entry points: observal, observal-shim, observal-proxy, observal-tui; deps: typer, httpx, rich, textual
- `observal-server/pyproject.toml` — deps include redis[hiredis], arq, strawberry-graphql[fastapi]
- `observal-server/config.py` — REDIS_URL setting added

## Bugs Fixed During Session

1. **Worker crash**: Changed `python -m worker` → `uv run arq worker.WorkerSettings` in docker-compose
2. **GraphQL DataLoaders empty**: Removed duplicate `FORMAT JSON` (was in both DataLoader SQL and `_ch_json` helper)
3. **Missing package-lock.json**: Generated for web app (npm ci needs it)
4. **Missing REDIS_URL**: Added to .env
5. **Stale uv.lock**: Regenerated with redis, arq, strawberry deps
6. **Demo ClickHouse auth**: Added user/password params to all ClickHouse HTTP queries

## What's Left

| Phase | What | Notes |
|-------|------|-------|
| 11 — Testing & CI | GitHub Actions, Playwright | Dev process, not product |
| 12 — Auth / SSO | Keycloak, OIDC, scoped keys, RBAC | Big scope, needs design review |
| 14 — ITJ | Information-Theoretic Judge | Research, replaces LLM-as-judge |
| 15 — Release Engineering | Compiled binaries, package registries | Distribution |

## How to Run

```bash
# Start Docker stack
cd docker && docker compose up -d

# Install CLI
cd .. && uv tool install --editable . --force

# Init (if fresh DB)
observal init

# Run demo
bash demo/run_demo.sh

# Launch TUI
observal tui
# or: observal-tui

# Run tests
cd observal-server && uv run --with pytest --with pytest-asyncio --with pyyaml --with typer --with rich --with textual pytest ../tests/ -q

# CLI commands
observal traces --limit 10
observal spans <trace-id>
observal list
observal whoami
```

## Architecture Summary

```
IDE (Kiro/Claude/Cursor/etc.)
    ↕ stdio (JSON-RPC)
observal-shim (transparent wrapper)
    ├── passes all messages through untouched
    ├── pairs requests/responses → spans
    ├── caches tools/list for schema compliance
    ├── buffers spans (flush every 5s or 50)
    ├── async fire-and-forget POST to server
    ↕ stdio
Actual MCP Server (unchanged, unaware)

Server Stack:
├── FastAPI API (port 8000)
│   ├── REST: auth, mcps, agents, review, telemetry, feedback, eval, admin
│   ├── GraphQL: /api/v1/graphql (Strawberry + DataLoaders + subscriptions)
│   └── Ingestion: POST /api/v1/telemetry/ingest
├── PostgreSQL 16 (users, mcps, agents, feedback, eval runs)
├── ClickHouse (traces, spans, scores — new; mcp_tool_calls, agent_interactions — legacy)
├── Redis 7 (pub/sub for subscriptions, arq job queue)
├── arq Worker (background eval jobs)
├── Vite + React Web UI (port 3000, urql GraphQL client)
└── Textual TUI (observal-tui, queries GraphQL + REST)
```
