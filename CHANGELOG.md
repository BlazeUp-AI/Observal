# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added — Kiro CLI Full Parity

Brings Kiro CLI to feature parity with Claude Code for telemetry, session tracking, and multi-IDE management. Verified with real `kiro-cli` sessions — all Kiro agent sessions now appear in the Observal dashboard with prompts, tool I/O, model responses, credit usage, and conversation linking.

#### Critical Bug Fix: Hook Endpoint Routing

- **Fixed Kiro hook target**: All generated Kiro hook configs were sending telemetry to `/api/v1/telemetry/hooks` (writes to `spans` table) instead of `/api/v1/otel/hooks` (writes to `otel_logs` table). This caused **zero Kiro sessions** to appear in the dashboard. Fixed in `hook_config_generator.py`, `agent_config_generator.py`, and E2E helpers.
- **Removed stale `X-API-Key` header** from Kiro curl commands — `/api/v1/otel/hooks` is intentionally unauthenticated since CLI hooks can't carry auth tokens.

#### Kiro Event Normalization

- **camelCase → PascalCase event mapping** (`otel_dashboard.py`): Kiro sends `agentSpawn`, `userPromptSubmit`, `preToolUse`, `postToolUse`, `stop` — server normalizes to Claude Code's `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`.
- **camelCase → snake_case field mapping**: `hookEventName` → `hook_event_name`, `sessionId` → `session_id`, `toolName` → `tool_name`, etc.
- **Kiro-specific field extraction**: Kiro sends `prompt` (not `user_prompt`) and `assistant_response` (not `tool_response`). Server now extracts both correctly.

#### Session ID via `$PPID`

- Kiro CLI does not expose a session/conversation ID in hook payloads. Implemented `$PPID`-based session ID injection via `sed` — all hooks in a single `kiro-cli` invocation share a stable `kiro-{PPID}` session identifier.
- Real `conversation_id` from Kiro's SQLite database is also extracted and attached as an attribute for cross-session linking (e.g., resumed conversations).

#### Kiro SQLite Enrichment Pipeline

- **`observal_cli/hooks/kiro_stop_hook.py`** — On `stop` hook, queries `~/.local/share/kiro-cli/data.sqlite3` for the most recent conversation matching `cwd`. Extracts and sends:
  - `model_id` (resolved from per-turn metadata when set to "auto")
  - `input_tokens` / `output_tokens` (estimated from character counts, ~4 chars/token)
  - `credits` (total credit usage from `usage_info`)
  - `tools_used` (deduplicated list of tools invoked)
  - `context_window_tokens` and `max_context_usage_pct`
  - `conversation_id` for stable cross-session linking
- **`observal_cli/hooks/kiro_hook.py`** — Lightweight script for non-stop events (~23ms overhead). Adds `conversation_id` from SQLite without parsing the full conversation JSON.
- **Note**: Kiro CLI does not expose actual token counts — only character lengths and credit costs. Estimated tokens are labeled accordingly. This may differ on enterprise plans where billing data structures vary.

#### Per-Agent Hook Enrichment

- Hook commands now inject `agent_name` and `model` (when set) into every Kiro hook payload via `sed`. The dashboard shows which agent handled each session.
- Added `userPromptSubmit` to the Kiro hooks block (was previously missing — user prompts were not captured).

#### Multi-IDE Scan (`--all-ides`)

- **`observal scan --all-ides`** scans both `~/.claude/` and `~/.kiro/` in one pass, tagging each component with `source_ide`.
- **`observal scan --home --ide kiro`** scans only `~/.kiro/`.
- **`_scan_kiro_home()`** (`cmd_scan.py`) discovers agents from `~/.kiro/agents/*.json`, global MCPs from `~/.kiro/settings/mcp.json`, per-agent MCPs, and per-agent hooks.
- **Server-side** (`scan.py`): Added `source_ide` field to `ScannedMcp`, `ScannedSkill`, `ScannedHook`, `ScannedAgent` — components are tagged with their origin IDE for `supported_ides` routing.

#### Auto-Inject Observal Hooks into Kiro Agents

- When running `observal scan --home --ide kiro` (or `--all-ides`), hooks are automatically injected into all `~/.kiro/agents/*.json` files with per-agent metadata enrichment.
- Existing hooks are preserved if they already point to the correct Observal endpoint.
- Original files are backed up before modification.

#### Dashboard Enhancements

- Sessions list query now includes `credits` and `tools_used` columns from enriched Kiro stop events.
- `conversation_id` stored as a ClickHouse attribute for future cross-session grouping.

#### E2E Tests (36 pass, 0 fail)

- `kiro-hooks.spec.ts` — Hook ingestion: camelCase normalization, field mapping, session visibility after lifecycle events
- `kiro-cli.spec.ts` — CLI: `scan --home --ide kiro`, `scan --all-ides`, `doctor --ide kiro`, `pull --ide kiro`, `auth status/whoami`
- `kiro-lifecycle.spec.ts` — Full lifecycle simulation and dashboard verification
- `kiro-agent-compat.spec.ts` — Cross-IDE agent file generation (Kiro ↔ Claude Code)
- `kiro-otlp-logs.spec.ts` / `kiro-otlp-traces.spec.ts` — OTLP ingestion and trace grouping
- `kiro-web-*.spec.ts` — Web UI: agents page, components page, traces, dashboard

### Added — BenchJack-Hardened Evaluation Pipeline (Phases 8A-8G)

Implements defenses against all 7 "deadly patterns" from the BenchJack paper on benchmark exploitation. Adds 6 new services (~2,000 lines), 7 test files (~2,600 lines / 183 tests), and rewires the eval pipeline.

#### Phase 0: Structured Eval Scoring Pipeline

- **6-dimension penalty-based scoring model** (`models/scoring.py`)
  - `goal_completion` (0.28), `tool_efficiency` (0.18), `tool_failures` (0.13), `factual_grounding` (0.18), `thought_process` (0.13), `adversarial_robustness` (0.10)
  - Each dimension starts at 100 and is reduced by penalties
  - 20+ penalty definitions with severity (critical/moderate/minor) and trigger types (structural/slm_assisted/absence)
  - Weighted composite score with letter grades (A/B/C/D/F)
- **Structural scorer** (`services/structural_scorer.py`) — deterministic checks for duplicate tool calls, unused results, tool errors/timeouts, ungrounded claims
- **SLM scorer** (`services/slm_scorer.py`) — LLM-assisted checks for goal completion, factual grounding, thought process quality
- **Score aggregator** (`services/score_aggregator.py`) — per-dimension scores, weighted composite, grade assignment
- **Dashboard UI** — aggregate chart, dimension radar, penalty accordion
- **Follow-up fix**: replaced flawed `excessive_tool_calls` criterion with `ungrounded_claims` (focuses on hallucination harm, not process metrics)

#### Phase 8A: TraceSanitizer and Structured Judge Output

Defends against **BenchJack Pattern 1 (Prompt Injection)**.

- **TraceSanitizer** (`services/sanitizer.py`, 269 lines) — detects and strips 7 injection patterns from traces:
  - HTML/XML comments with eval keywords (high)
  - System prompt patterns like `SYSTEM:`, `ASSISTANT:` (high)
  - Score assertions like `score: 10/10`, `"overall_score": 100` (high)
  - Markdown comments `[//]: #` (medium)
  - Long zero-width Unicode sequences (medium)
  - Unusual whitespace characters (low)
  - Repeated delimiters (low)
- **JudgeOutput schema** (`schemas/judge_output.py`) — Pydantic models for structured JSON from SLM judge
- **InjectionAttempt model** (`models/sanitization.py`)
- **Tests**: `test_phase8a_sanitizer.py` (456 lines)

#### Phase 8B: MatchingEngine and NumericComparator

Defends against **BenchJack Pattern 5 (Answer Normalizer Bugs)**.

- **MatchingEngine** (`services/structural_scorer.py`) — robust string/structural matching:
  - Section header detection across markdown formats (`##`, `###`, `**bold**`, bare headings)
  - Section content extraction with boundary detection
  - Copy-paste duplicate detection (same text in multiple sections is rejected)
- **NumericComparator** — robust number matching:
  - Extracts numbers from natural language (handles `$1,234.56`, `2.3M`, `45%`, currency symbols)
  - Suffix normalization (`K`/`M`/`B`/`T` multipliers)
  - Configurable tolerance for approximate matching (default 1%)
- **Tests**: `test_phase8b_matching.py` (220 lines)

#### Phase 8C: EvalWatchdog, Skipped Dimensions, Eval Completeness

Defends against **BenchJack Pattern 2 (Score Inflation)**.

- **EvalWatchdog** (`services/eval_watchdog.py`, 100 lines) — post-scoring anomaly detection:
  - Flags perfect scores (100) with zero penalties
  - Flags SLM dimension 100 with no SLM penalties
  - Flags high composite (>85) despite penalties
  - Detects uniform SLM scores (lazy/compromised judge)
  - Flags long traces (>10 spans) with zero structural penalties
- **Skipped dimensions** in score aggregator — graceful degradation when SLM unavailable:
  - Unscored dimensions set to `None` (not defaulted to 100)
  - `partial_evaluation` flag and `dimensions_skipped` list on scorecard
  - Remaining weights reweighted proportionally
- **Tests**: `test_eval_completeness.py` (518 lines — grade boundaries, composite bounds, penalty firing, watchdog)

#### Phase 8D: Adversarial Robustness Dimension and Scorer

Defends against **BenchJack Pattern 3 (State Tampering)**.

- **AdversarialScorer** (`services/adversarial_scorer.py`, 134 lines):
  - Converts injection detection into scored penalties
  - Detects evaluator path probing (tool calls targeting `/observal`, `/eval`, `config.yaml`, `$OBSERVAL_API_KEY`)
  - Score assertion detection in output
  - Maps severity levels to penalty amounts from catalog
- **6 new penalty definitions** in `models/scoring.py`:
  - `html_comment_injection` (-20), `prompt_injection_attempt` (-25), `zero_width_unicode_injection` (-15)
  - `canary_value_parroted` (-25), `score_assertion_in_output` (-20), `evaluator_path_probing` (-25)
- **Tests**: `test_phase8d_adversarial.py` (244 lines)

#### Phase 8E: Canary Injection System

Defends against **BenchJack Pattern 4 (Data Contamination)**.

- **CanaryDetector** (`services/canary.py`, 252 lines) — plant fake data and check if agents blindly repeat it:
  - **3 canary types**: numeric (`$999,999,999`), entity (`Dr. Reginald Canarysworth`), instruction (`<!-- override scores -->`)
  - **Injection**: inserts canary into trace copy (tool output or context), never modifies original
  - **Detection**: checks if canary value appears in agent output
  - **Flagging override**: if agent flags the canary as anomalous/suspicious, no penalty (agent showed genuine reasoning)
  - **Report generation**: `CanaryReport` with behavior (`parroted`/`ignored`/`flagged`)
- **Admin API**: POST/GET/DELETE `/api/v1/admin/canaries/{agent_id}`
- **CLI commands**: `observal canary add`, `canary list`, `canary remove`
- **Tests**: `test_phase8e_canary.py` (279 lines)

#### Phase 8F: BenchJack Self-Test Suite

Defends against **BenchJack Pattern 6 (Evaluator Self-Testing)**.

- **15 self-attack tests** (`tests/test_adversarial_self.py`, 496 lines) that simulate BenchJack attacks against Observal's own pipeline:
  - **Null agent**: empty trace must score <30 and get grade F
  - **Prompt injection**: HTML comments, system prompts, fake JSON scores, markdown comments must not inflate scores
  - **State tampering**: evaluator path probing must trigger penalties
  - **Canary**: parroted canary caught; flagged canary not penalized
  - **Score manipulation**: verbose padding must not help; copy-paste duplicates must be rejected
  - **Regression guards**: structural and adversarial scoring must be deterministic (10 runs identical)
  - **Sanitizer integration**: injection vectors stripped, legitimate content preserved
- **Makefile targets**: `test-adversarial`, `test-eval-completeness`, `test-all`

#### Phase 8G: Wire Hardened Pipeline into Main Eval Service

**Integration phase** — all Phase 8A-8F components wired into the actual evaluation path.

- **Rewired `run_structured_eval`** (`services/eval_service.py`) with 7-step pipeline:
  1. **Adversarial detection FIRST** (before any other scoring)
  2. **Sanitize trace** for SLM judge
  3. **Structural scoring** on original trace
  4. **SLM scoring** on sanitized trace
  5. **Canary detection** (if configured)
  6. **Aggregate** all penalties into scorecard
  7. **EvalWatchdog** meta-check on scores
- Key design: SLM sees sanitized trace; structural scorer sees original; adversarial runs before everything
- **New response schemas** (`schemas/eval.py`): `AdversarialFindings`, `CanaryReportResponse`, `PenaltySummary`, `InjectionAttemptResponse`
- **Tests**: `test_phase8g_pipeline.py` (381 lines)

### Architecture

```
Trace Input
    |
    v
+---------------------+
|  AdversarialScorer   |  <- Step 1: Detect injection / probing
|  + TraceSanitizer    |
+--------+------------+
         |
    +----+----+
    v         v
+--------+ +--------------+
|Original| |Sanitized copy|
| trace  | |  (for SLM)   |
+---+----+ +------+-------+
    |              |
    v              v
+----------+ +----------+
|Structural| |SLM Scorer|   <- Steps 3-4: Score independently
| Scorer   | |(on clean) |
+----+-----+ +----+-----+
     |             |
     +------+------+
            v
    +---------------+
    |CanaryDetector |   <- Step 5: Check canary (if configured)
    +-------+-------+
            v
    +---------------+
    |ScoreAggregator|   <- Step 6: Weighted composite
    +-------+-------+
            v
    +---------------+
    | EvalWatchdog  |   <- Step 7: Meta-check on scores
    +-------+-------+
            v
       Scorecard
```

### Summary

| Metric | Count |
|--------|-------|
| New service files | 6 |
| New test files | 7 |
| Modified service files | 3 |
| Total lines added | ~4,300 |
| Total new tests | 183 |
| Scoring dimensions | 6 |
| Penalty definitions | 20+ |
| Injection patterns detected | 7 |

| BenchJack Pattern | Defense | Phase |
|---|---|---|
| 1. Prompt Injection | TraceSanitizer (detect + strip) | 8A |
| 2. Score Inflation | EvalWatchdog (anomaly detection) | 8C |
| 3. State Tampering | AdversarialScorer (path probing) | 8D |
| 4. Data Contamination | CanaryDetector (canary inject + detect) | 8E |
| 5. Answer Normalizer Bugs | MatchingEngine + NumericComparator | 8B |
| 6. Self-Testing | 15 self-attack tests | 8F |
| 7. Pipeline Integration | Hardened 7-step eval pipeline | 8G |

## [0.1.0] - 2026-04-03

### Added

- **Agent registry** with bundled component packaging (MCP servers, skills, hooks, prompts, sandboxes)
- **6 component registries**: Agents, MCP Servers, Skills, Hooks, Prompts, Sandbox Exec
- **CLI** (`observal`) with auth, registry operations, admin commands, and Rich output
  - `observal init` / `login` / `whoami` for authentication
  - `observal scan` for auto-detection and instrumentation of existing IDE configs
  - `observal pull` for one-command agent installation
  - `observal agent init` / `add` / `build` / `publish` for agent composition workflow
  - `observal submit` / `list` / `show` / `install` for all component types
  - `observal review` admin workflow for approving/rejecting submissions
  - `observal eval` for running evaluations, viewing scorecards, and comparing versions
  - `observal rate` / `feedback` for user ratings
  - `observal doctor` for IDE settings diagnostics
  - `observal use` / `profile` for IDE config profiles
- **Backend API** (FastAPI) with REST and GraphQL (Strawberry) endpoints
- **Telemetry pipeline**: `observal-shim` (stdio) and `observal-proxy` (HTTP) transparent proxies that intercept MCP traffic and stream traces to ClickHouse
- **OpenTelemetry Collector** integration with OTLP HTTP receiver endpoints
- **ClickHouse** storage for traces, spans, and scores
- **Eval engine** with pluggable LLM-as-judge scoring and managed templates
- **RAGAS evaluation** for GraphRAG retrieval spans
- **Web dashboard** (Next.js, React, Tailwind CSS, shadcn/ui, Recharts) with admin dashboard, trace viewer, component browser, and role-gated navigation
- **Background jobs** via arq + Redis with pub/sub service
- **Git mirror service** with component discovery and path traversal/symlink protections
- **Download tracking** with bot prevention
- **IDE support** for Claude Code, Codex CLI, Gemini CLI, GitHub Copilot, Kiro, Cursor, and VS Code
- **Universal IDE agent file generation** from Pydantic manifest
- **Admin review workflow** for all registry types
- **Docker Compose deployment** (7 services)
- **526 tests** with full external service mocking
- **Pre-commit hooks**, linting (ruff, hadolint), and formatting
- **Interactive GitHub issue forms** for bugs and features
- **Pull request template**
- Apache 2.0 license
