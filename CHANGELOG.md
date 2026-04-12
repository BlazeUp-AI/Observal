# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added — Kiro CLI Telemetry Support

Adds Kiro CLI as a supported telemetry source. Kiro sessions now appear in the dashboard with user prompts, tool I/O, model responses, credit tracking, and agent attribution. Not yet at full parity with Claude Code — see status table below.

#### Telemetry Status: Claude Code vs Kiro CLI

| Capability | Claude Code | Kiro CLI | Notes |
|---|---|---|---|
| Sessions in dashboard | **Full** | **Working** | Kiro uses `$PPID`-based session IDs (see below) |
| User prompts | **Full** | **Working** | Captured via `userPromptSubmit` hook |
| Model responses | **Full** | **Working** | Captured via `stop` hook `assistant_response` |
| Tool names + I/O | **Full** | **Working** | `preToolUse`/`postToolUse` with params and response |
| Token counts | **Full** (`input_tokens`, `output_tokens`, `cache_read_tokens`) | **Not available** | Kiro CLI does not expose token counts anywhere — not in hooks, not in its SQLite DB. Only credits. |
| Cost tracking | `cost_usd` per API call (not yet aggregated to session level) | **Credits** (session-level, from SQLite DB) | Dashboard shows credits for Kiro, tokens for Claude Code |
| Model name | **Full** | **Working** | Resolved from Kiro SQLite, often shows "auto" |
| Agent attribution | `agent_id`, `agent_type` from subagents | `agent_name` only | Kiro has no agent_id/agent_type concept |
| Session continuations | Native `session_id` (UUID) persists across resumes | `$PPID` changes on each `kiro-cli` invocation | `conversation_id` from SQLite is attached as an attribute but NOT used as session_id — resumed Kiro sessions appear as separate sessions |
| User identity | `user.id` captured | Not available | Kiro hooks don't include user identity |
| IDE/terminal info | `terminal.type` captured | Not available | |
| Permission mode | Captured | Not available | |
| Subagent tracking | `SubagentStart`/`SubagentStop` events | Not available | Kiro has no subagent hook events |
| Task tracking | `TaskCreated`/`TaskCompleted` events | Not available | |
| Eval engine support | **Working** — traces feed into structured eval pipeline | **Not working** — hook data goes to `otel_logs`, eval reads from `agent_interactions` table | Needs a bridge layer (see Known Gaps) |

#### Known Gaps

- **Session continuations broken for Kiro**: When a user does `kiro-cli chat --resume`, a new `$PPID` is assigned, creating a separate session in the dashboard. The real `conversation_id` from Kiro's SQLite DB is captured as an attribute on each event, but the dashboard doesn't yet group sessions by `conversation_id`. Fix requires: session grouping/linking in the dashboard query.
- **Eval engine cannot score Kiro sessions**: The eval pipeline (`run_structured_eval`) reads from the `agent_interactions` and `spans` tables, which expect structured span data with `type`, `input`, `output`, `status` fields. Kiro hook events are flat log entries in `otel_logs` — no bridge exists to convert them into eval-compatible spans. Fix requires: a materializer that converts `otel_logs` hook events into structured spans, or a new eval path that reads directly from `otel_logs`.
- **Per-agent trace isolation incomplete**: The ClickHouse schema has indexed `agent_id` columns on both `spans` and `traces` tables, and `otel_logs` stores `agent_name` in `LogAttributes`. But no API endpoint exists to query "all traces/spans where this agent participated" — the eval endpoint requires a `trace_id` first, then fetches spans. For agent-level evals, we need: `GET /api/v1/agents/{id}/traces` that queries across both `otel_logs` (hook data) and `spans` (shim data).

#### What Was Implemented

**Critical bug fix**: All generated Kiro hook configs were pointing to `/api/v1/telemetry/hooks` (writes to `spans` table) instead of `/api/v1/otel/hooks` (writes to `otel_logs` table). This caused zero Kiro sessions in the dashboard.

**Event normalization** (`otel_dashboard.py`):
- camelCase → PascalCase event mapping (`agentSpawn` → `SessionStart`, `postToolUse` → `PostToolUse`, etc.)
- camelCase → snake_case field mapping (`hookEventName` → `hook_event_name`, `sessionId` → `session_id`, etc.)
- Kiro-specific field extraction: `prompt` → `tool_input`, `assistant_response` → `tool_response`

**SQLite enrichment pipeline**:
- `kiro_stop_hook.py` — On `stop` event, queries `~/.local/share/kiro-cli/data.sqlite3` for the most recent conversation matching `cwd`. Extracts: `model_id`, `credits`, `tools_used`, `turn_count`, `conversation_id`.
- `kiro_hook.py` — Lightweight script (~23ms) for non-stop events. Adds `conversation_id` from SQLite.
- Session IDs use `$PPID` (Kiro doesn't expose any session identifier in hook payloads).

**Per-agent hook enrichment**: Hook commands inject `agent_name` and `model` into every payload via `sed`. Added `userPromptSubmit` to hooks (was missing — prompts weren't captured before).

**Multi-IDE scan** (`--all-ides`):
- `observal scan --all-ides` scans `~/.claude/` and `~/.kiro/` in one pass with `source_ide` tagging.
- `_scan_kiro_home()` discovers agents, MCPs, and hooks from `~/.kiro/`.
- Auto-injects Observal hooks into all `~/.kiro/agents/*.json` files.

**Dashboard**: Kiro sessions show credits (orange) instead of token counts. `tools_used` shown in "Tokens Out" column for Kiro rows.

**E2E tests**: 36 pass, 0 fail — hooks, CLI commands, lifecycle, cross-IDE compat, OTLP ingestion, web UI.

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
