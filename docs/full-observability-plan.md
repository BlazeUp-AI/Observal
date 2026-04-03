# Observal Full Observability Plan

> Goal: Be Langfuse but better — with MCP registry, agent registry, and IDE integration as differentiators. Full AI observability for traces, sessions, tool calls, generations, RAG, agents, hooks, prompts.

## Current State

**What works**: MCP shim captures tool calls transparently. ClickHouse schema has fields for tokens, cost, sessions, parent spans, input/output. Ingestion endpoint accepts batch traces/spans/scores. GraphQL for querying. Eval engine with LLM-as-judge.

**What's broken**: Dashboard is bare-bones. Only MCP JSON-RPC span types. No sessions page. No generation tracking. No cost. No filters. No trace tree view. No prompt versioning. No user analytics.

## No SDK Required

The shim captures MCP telemetry with zero code changes. For deeper instrumentation (LLM calls inside MCP servers, RAG pipelines), we'll add optional span enrichment via the ingestion API — MCP server authors can POST additional spans to the same trace. SDK is deferred.

## Phase 1: Span Type Expansion

Expand what the shim captures and what the ingestion API accepts.

**New span types** (all go through existing spans table):
- `generation` — LLM call (model, tokens, cost, prompt, completion)
- `retriever` — RAG/GraphRAG retrieval (query, documents, entities, relationships)
- `agent` — Agent reasoning/decision step
- `tool` — Generic tool call (already have this for MCP, generalize)
- `embedding` — Embedding generation
- `hook` — IDE hook execution (PreToolUse, PostToolUse, Stop)
- `sandbox` — Code execution / sandbox run

**Schema changes** (add columns to spans table):
- `model` LowCardinality(String) — model name for generations
- `completion_start_time` Nullable(DateTime64(3)) — time to first token
- `prompt_name` Nullable(String) — linked prompt
- `prompt_version` Nullable(UInt32) — linked prompt version

**Shim improvements**:
- Extract model info from MCP tool responses when available
- Track hook executions if the IDE reports them
- Set parent_span_id for nested tool calls within a session

## Phase 2: Sessions & Conversations

Sessions group traces into conversations. Derived from traces (no new table needed — Langfuse does it this way too).

**What changes**:
- Session list: aggregate from traces WHERE session_id IS NOT NULL, GROUP BY session_id
- Session detail: all traces for a session in timeline order
- Session metrics: trace count, total duration, total tokens, total cost
- GraphQL: `sessions` query, `session(id)` with nested traces
- CLI: `observal sessions`, `observal session <id>`
- Web UI: Sessions page with table, click to see conversation timeline

## Phase 3: Prompt Management

Version-controlled prompts linked to agents and traces.

**What changes**:
- PostgreSQL tables: `prompts` (name, current_version), `prompt_versions` (prompt_id, version, content, model_config, created_by, created_at)
- Prompts are the agent system prompts we already store — just add versioning
- When an agent is updated, a new prompt version is created automatically
- Generation spans can reference prompt_name + prompt_version
- API: CRUD for prompts, version history
- CLI: `observal prompt list`, `observal prompt show <name>`, `observal prompt versions <name>`
- Web UI: Prompts page with version history, diff view

## Phase 4: Dashboard Rewrite (Langfuse-quality)

The web UI needs to go from "generic AI dashboard" to "Langfuse-level product."

### Navigation (Langfuse-style sidebar)
- Home / Dashboard
- Tracing (traces list)
- Sessions
- MCP Servers (our unique)
- Agents (our unique)
- Prompts
- Scores
- Evaluations
- Users
- Settings

### Dashboard / Home page
- Stat cards: total traces, total spans, total tokens, total cost, active users
- Traces over time (area chart)
- Cost over time (area chart)
- Top models by usage (bar chart)
- Top tools by call count (bar chart)
- Latency percentiles (bar chart)
- Error rate trend

### Traces page (Langfuse-style)
- Filterable table: name, type, session, user, tokens, cost, latency, scores, tags
- Date range picker
- Filter by: trace type, model, user, session, tags, metadata
- Column visibility toggle
- Click row → trace detail

### Trace detail page (Langfuse-style)
- **Trace tree view**: visual hierarchy of spans (not just a flat table)
  - Indented tree showing parent → child span relationships
  - Each span shows: type icon, name, latency bar, status badge, token count
  - Click span to expand: full input/output, metadata, scores
- Trace metadata panel: tags, user, session, timestamps
- Scores panel
- Timeline waterfall view (spans as horizontal bars showing timing)

### Sessions page
- Table: session ID, trace count, duration, user, first/last activity, total tokens, total cost
- Click → session detail with conversation timeline
- Each trace in the session shown as a card with summary

### MCP Servers page (our unique)
- Registry browser with search, category filter
- Per-MCP: metrics (calls, errors, latency), recent traces, feedback
- Install button with IDE picker

### Agents page (our unique)
- Agent list with model, version, MCP links
- Per-agent: metrics, recent traces, eval scorecards, prompt history
- Install button with IDE picker

### Prompts page
- List prompts with current version, linked agents
- Version history with diff
- Performance comparison across versions (latency, cost, scores)

### Scores page
- All scores across traces (human ratings, eval scores, API scores)
- Filter by source, name, value range
- Score distribution charts

### Users page
- List users with trace count, total cost, last active
- Click → user's traces

### Evaluations page
- Eval runs with scorecards
- Dimension breakdown
- Version comparison
- Bottleneck detection

## Phase 5: Cost & Token Tracking

**Model registry** (PostgreSQL):
- `models` table: name, provider, input_cost_per_token, output_cost_per_token, unit
- Pre-seed with ~30 common models (GPT-4o, Claude Sonnet, Gemini, Llama, Mistral, etc.)
- Auto-calculate cost on ingestion when generation span has usage but no cost
- Dashboard: cost breakdown by model, by user, by day

## Phase 6: Datasets & Experiments

Structured evaluation datasets.

- `datasets`, `dataset_items`, `dataset_runs`, `dataset_run_items` tables
- API: CRUD for datasets, run experiments against items
- CLI: `observal dataset list`, `observal dataset run <id>`
- Web UI: dataset browser, experiment comparison view

## Priority Order

| # | Phase | Why |
|---|-------|-----|
| 1 | Dashboard rewrite (Phase 4) | Most visible, most broken. Users see this first. |
| 2 | Sessions (Phase 2) | Conversations are expected. Low backend effort (derived from traces). |
| 3 | Span types (Phase 1) | Enables richer trace views. Schema changes are small. |
| 4 | Cost & tokens (Phase 5) | Core value prop. Model registry + auto-calculation. |
| 5 | Prompts (Phase 3) | Builds on existing agent prompts. Versioning + linking. |
| 6 | Datasets (Phase 6) | Advanced use case. Enterprise feature. |

## What We Have That Langfuse Doesn't

- **MCP Server Registry**: submit, validate, review, distribute. Langfuse has zero MCP awareness.
- **Agent Registry**: bundled configs with goal templates, MCP linking, per-IDE generation.
- **Transparent Shim**: zero-code telemetry capture for any MCP server.
- **IDE Config Generation**: one-click install for 6 IDEs.
- **CLI-first**: every operation available via CLI.
- **GraphRAG-aware spans**: entities_retrieved, relationships_used, hop_count fields already in schema.
