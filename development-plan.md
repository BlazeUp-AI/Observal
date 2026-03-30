# Observal — Development Strategy

**Team Size:** 2-3 engineers
**Tools:** Kiro Pro + Claude Code for development
**Approach:** CLI-first, Web UI second. Ship thin, iterate fast.

---

## Phase Overview

```
Phase 1: Foundation          ░░░░░░░░  (~2-3 weeks)
Phase 2: MCP Registry        ░░░░░░░░░░  (~3-4 weeks)
Phase 3: Agent Registry      ░░░░░░░░  (~2-3 weeks)
Phase 4: Hooks & Telemetry   ░░░░░░░░░░  (~3-4 weeks)
Phase 5: Dashboards          ░░░░░░░░  (~2-3 weeks)
Phase 6: Feedback            ░░░░░  (~1-2 weeks)
Phase 7: Eval Engine         ░░░░░░░░░░░░  (~4-5 weeks)
Phase 8: Web UI              ░░░░░░░░░░  (~3-4 weeks)
                                              Total: ~20-28 weeks
```

**Critical path:** Phase 1 → 2 → 3 → 4 → 5 → 7
**Parallel track (once Phase 2 lands):** Phase 6 and Phase 8 can start

---

## Phase 1: Foundation

**Goal:** A running Docker stack with database, API skeleton, and simple auth. Everything else builds on this.

### Deliverables
- `docker-compose.yml` with all services booting cleanly
- Python FastAPI backend with health check endpoint
- PostgreSQL running with initial migration framework (Alembic)
- ClickHouse running with telemetry schema stub
- Simple auth: API key-based authentication for CLI, session tokens for future Web UI
- Three roles in the DB model: Admin, Developer, User (enforcement is just a role field on the user record for now — no complex RBAC middleware yet)
- First-run setup flow: `observal init` creates the admin account and generates API keys
- `.env` configuration for all service credentials and settings

### Technical Tasks

```
1. Project scaffolding
   ├── /observal-server        (FastAPI app)
   │   ├── /api                (route modules)
   │   ├── /models             (SQLAlchemy models)
   │   ├── /services           (business logic)
   │   ├── /schemas            (Pydantic request/response schemas)
   │   └── /migrations         (Alembic)
   ├── /observal-cli           (Python CLI using Click or Typer)
   ├── /hooks                  (hook scripts, one folder per IDE/CLI)
   ├── /docker                 (Dockerfiles, compose, nginx configs)
   └── /docs

2. Docker Compose setup
   - observal-api (FastAPI, uvicorn)
   - observal-db (PostgreSQL 16)
   - observal-clickhouse (ClickHouse latest)
   - Volumes for persistent data
   - Internal network between services

3. Database models (PostgreSQL)
   - users (id, email, name, role, api_key_hash, created_at)
   - enterprise_config (key-value settings table)

4. Auth middleware
   - API key validation for CLI requests (X-API-Key header)
   - Role check decorator (@require_role("admin"))
   - No SSO/SAML yet — that's a later enhancement on this foundation

5. CLI skeleton
   - observal init (first-run setup)
   - observal login (authenticate, store API key locally in ~/.observal/config)
   - observal whoami (verify auth)
```

### Definition of Done
- `docker compose up -d` starts everything
- `observal init` creates admin user
- `observal login` authenticates against the server
- `observal whoami` returns user info
- API returns 401 for unauthenticated requests

---

## Phase 2: MCP Registry

**Goal:** Developers can submit FastMCP (Python) servers via CLI, Observal validates the manifest, admin approves, and users can browse and get install configs.

### Deliverables
- `observal submit <GIT_URL>` command with interactive metadata prompts
- FastMCP manifest validation (tools, descriptions, input schemas)
- Admin approval flow via CLI (`observal review list`, `observal review approve/reject <id>`)
- `observal list` to browse the registry
- `observal install <mcp-id> --ide <cursor|claude-code|kiro|gemini-cli>` generates config snippet
- Download tracking (incremented when config is generated)

### MCP Declaration Standard (FastMCP on Python)

This is the "detailed process for how MCPs should be declared" — what Observal expects to find when it clones the repo:

```
Required repo structure for FastMCP (Python):
├── src/
│   └── server.py          (or any .py with FastMCP server definition)
├── requirements.txt       (or pyproject.toml)
└── README.md              (optional but recommended)

What Observal extracts from the FastMCP server:
1. Server name and description (from @mcp.server() decorator or FastMCP() constructor)
2. Tool definitions:
   - Tool name (from @mcp.tool() decorator)
   - Tool description (from docstring or description param)
   - Input schema (from function type hints / Pydantic models)
   - Output type
3. Resource definitions (if any)
4. Prompt templates (if any)

Validation rules:
- Server must have a name and non-empty description
- Every tool must have a description (min 20 chars)
- Every tool must have typed input parameters (no **kwargs without schema)
- Server must be importable without runtime errors (Observal does a dry import in sandbox)
```

### Metadata Collected via CLI Prompts (not from repo)

When a developer runs `observal submit`, after the repo is cloned and validated, they're prompted for:

```
? MCP Server Name: [pre-filled from FastMCP server name]
? Version (semver): 1.0.0
? Category: [select from enterprise-defined list]
? Description: [pre-filled from server description, editable]
? Owner / Team: 
? Supported IDEs: [multi-select: cursor, kiro, claude-code, gemini-cli]
? Setup instructions (or press Enter to auto-generate):
? Changelog for this version:
? [Any enterprise custom fields configured by admin]
```

### Config Snippet Generation

When a user runs `observal install <mcp-id> --ide cursor`, Observal generates:

**For Cursor / VS Code:**
```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "python",
      "args": ["-m", "<module_path>"],
      "env": {}
    }
  }
}
```

**For Claude Code:**
```bash
claude mcp add <server-name> -- python -m <module_path>
```

**For Kiro:**
```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "python",
      "args": ["-m", "<module_path>"],
      "env": {}
    }
  }
}
```

**For Gemini CLI:**
```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "python",
      "args": ["-m", "<module_path>"]
    }
  }
}
```

Config format details will evolve as IDEs update — this is the abstraction layer Observal maintains.

### Technical Tasks

```
1. Database models
   - mcp_listings (id, name, version, git_url, description, category,
     owner, supported_ides, setup_instructions, changelog,
     status [pending|approved|rejected], created_at, updated_at)
   - mcp_custom_fields (listing_id, field_name, field_value)
   - mcp_downloads (listing_id, user_id, ide, downloaded_at)
   - mcp_validation_results (listing_id, stage, passed, details, run_at)

2. Submission service
   - Clone git repo to temp directory
   - Detect FastMCP server entry point (scan for FastMCP() or @mcp.server)
   - Parse server: extract name, description, tools, resources, prompts
   - Validate against rules (descriptions present, types present, importable)
   - Store validation results
   - Create listing record with status=pending

3. CLI commands
   - observal submit <GIT_URL> (clone, validate, prompt for metadata, submit)
   - observal review list (admin only — show pending submissions)
   - observal review show <id> (admin — show details + validation results)
   - observal review approve <id> (admin — publish to registry)
   - observal review reject <id> --reason "..." (admin — reject with feedback)
   - observal list [--category X] [--search "query"] (browse registry)
   - observal show <mcp-id> (show full details of a listing)
   - observal install <mcp-id> --ide <ide> (generate config snippet)

4. Config generator service
   - Template per IDE/CLI
   - Fill in server name, command, args, env from listing metadata
   - Increment download counter
```

### Definition of Done
- Developer can submit a FastMCP repo and get validation feedback
- Admin can review and approve/reject via CLI
- User can list, search, view details, and generate IDE config for any approved MCP
- Download count increments on each `observal install`

---

## Phase 3: Agent Registry

**Goal:** Developers can register agents (Prompt + MCP servers + Model config) with a goal template, and users can install them across supported IDEs/CLIs.

### Deliverables
- `observal agent create` command with interactive prompts
- Agent definition links to existing MCP servers in the registry
- Goal template entry (structured: required output sections)
- `observal agent list` and `observal agent install <agent-id> --ide <ide>`
- Config generation for agents across Gemini CLI, Claude Code, and Kiro

### What an Agent Looks Like in Observal

An agent is NOT a Git repo (unlike MCP servers). It's a configuration object assembled within Observal:

```yaml
agent:
  name: "Incident Analyzer"
  version: "1.0.0"
  description: "Analyzes support cases for root cause, similar incidents, and triage"
  owner: "Platform Team"
  
  prompt: |
    You are an incident analysis agent. When given an incident ID,
    you will analyze the support case and produce:
    1. Root cause analysis
    2. Similar past incidents
    3. Recommended next steps
    4. Component triage assignment
    Always cite your sources. For any numeric threshold, include
    the source document where the value was found.
  
  mcp_servers:
    - id: "incident-rag-mcp"       # must exist in MCP registry
    - id: "jira-mcp"
    - id: "triage-docs-mcp"
    - id: "knowledge-graph-mcp"
  
  model:
    name: "claude-sonnet-4"
    max_tokens: 4096
    temperature: 0.2
  
  goal_template:
    description: "Analyze support case and produce structured analysis"
    required_output_sections:
      - name: "Root Cause"
        grounding_required: true
      - name: "Similar Incidents"
        grounding_required: true
      - name: "Next Steps"
        grounding_required: false
      - name: "Triaged Component"
        grounding_required: true

  supported_ides:
    - gemini-cli
    - claude-code
    - kiro
```

### Agent Config Generation

Unlike MCP servers which are tool configs, an agent install generates a more complete setup — rules files, system prompts, and MCP configs bundled together.

**For Claude Code:**
```markdown
# .claude/rules/incident-analyzer.md (CLAUDE.md rules file)
<system_prompt>
[Agent prompt from Observal]
</system_prompt>

# Plus MCP configs for all referenced MCP servers
```
```bash
# CLI commands to set up
claude mcp add incident-rag-mcp -- python -m incident_rag
claude mcp add jira-mcp -- python -m jira_connector
# ... etc
```

**For Kiro:**
```markdown
# .kiro/rules/incident-analyzer.md (Kiro steering rules)
[Agent prompt from Observal]

# Plus .kiro/mcp.json with all referenced MCP servers
```

**For Gemini CLI:**
```markdown
# GEMINI.md or gemini rules file
[Agent prompt from Observal]

# Plus MCP server configurations in Gemini settings
```

The key insight: Observal is the **single source of truth** for the agent definition. Each IDE gets a different packaging format, but the content is identical.

### Technical Tasks

```
1. Database models
   - agents (id, name, version, description, owner, prompt,
     model_name, model_config, status, created_at, updated_at)
   - agent_mcp_links (agent_id, mcp_listing_id, order)
   - agent_goal_templates (agent_id, description)
   - agent_goal_sections (goal_template_id, name, description,
     grounding_required, order)
   - agent_downloads (agent_id, user_id, ide, downloaded_at)

2. Agent service
   - Validate all referenced MCP servers exist and are approved
   - Validate goal template has at least one section
   - Store agent definition

3. CLI commands
   - observal agent create (interactive: name, prompt, select MCPs
     from registry, model config, goal template sections, supported IDEs)
   - observal agent list [--search "query"]
   - observal agent show <agent-id>
   - observal agent install <agent-id> --ide <ide>
   - observal agent update <agent-id> (edit fields, bump version)

4. Agent config generator
   - Template per IDE/CLI
   - Bundle: prompt → rules file, MCP servers → config file
   - Generate setup instructions
```

### Definition of Done
- Developer can create an agent that references approved MCP servers
- Developer can define a goal template with required output sections
- User can install an agent for Gemini CLI, Claude Code, or Kiro
- Install generates all necessary files (rules, MCP configs, setup instructions)
- Agent listing shows linked MCP servers and goal template

---

## Phase 4: Hooks & Telemetry

**Goal:** Agents installed from Observal automatically report telemetry back to the server. Developers can see that data is flowing.

### Deliverables
- Hook scripts for Claude Code, Gemini CLI, Kiro, and Cursor
- Shared collector library (Python package)
- Telemetry ingestion API endpoint on the server
- ClickHouse schema for storing telemetry events
- `observal telemetry status` command to verify data is flowing
- Hooks are automatically included in generated agent/MCP configs

### How Hooks Work (Langfuse-style)

The approach is similar to Langfuse: instrument the agent/MCP interaction and ship traces to a backend. But instead of SDK-level instrumentation, we use IDE/CLI-native hooks.

**Claude Code:**
Claude Code supports hooks natively (pre/post tool use events).

```json
// .claude/settings.json — hooks section
{
  "hooks": {
    "postToolUse": [
      {
        "command": "python -m observal.hooks.claude_code post_tool_use"
      }
    ]
  }
}
```

The hook script receives the tool call details via stdin/env, packages it as a telemetry event, and streams it to the Observal server.

**Kiro:**
Kiro hook integration via its lifecycle hook system (specifics TBD based on Kiro's hook API — build adapter once API is documented).

**Gemini CLI:**
Gemini CLI hook integration via its callback system.

**Cursor / VS Code:**
VS Code extension that listens to MCP-related events and reports telemetry.

### Collector Library

Shared Python package (`observal-collector`) that all hook scripts use:

```python
# What each hook script does:
from observal.collector import ObservalCollector

collector = ObservalCollector(
    server_url="https://observal.internal",
    api_key="...",  # from ~/.observal/config
)

# Called by the hook script with event data
collector.track_tool_call(
    mcp_server_id="jira-mcp",
    tool_name="get_issue",
    input_params={...},
    response={...},
    latency_ms=234,
    status="success",
    user_action="accepted",  # if available from the IDE
    session_id="...",
    ide="claude-code",
)
```

The collector handles: JSON serialization, real-time HTTP streaming to the ingestion endpoint, local buffering on failure, retry logic.

### Auto-Integration with Configs

When a user runs `observal install` or `observal agent install`, the generated config automatically includes hook setup. The user doesn't manually configure hooks — they come pre-wired.

This means the config generator from Phase 2 and 3 needs to be updated to inject hook configurations alongside the MCP/agent configs.

### Technical Tasks

```
1. Telemetry ingestion API
   - POST /api/v1/telemetry/events (accepts single event or batch)
   - Validates event schema
   - Writes to ClickHouse

2. ClickHouse schema
   - mcp_tool_calls table (all fields from telemetry schema in spec)
   - agent_interactions table (all fields from agent interaction schema)
   - session_summaries table
   - Partitioned by date, ordered by timestamp

3. Collector library (observal-collector Python package)
   - ObservalCollector class
   - track_tool_call() method
   - track_agent_interaction() method
   - track_session_summary() method
   - Real-time HTTP streaming (POST per event)
   - In-memory buffer with disk spillover on failure
   - Retry with exponential backoff
   - Reads server_url and api_key from ~/.observal/config

4. Hook scripts (one per IDE/CLI)
   - hooks/claude_code/    — reads Claude Code hook event, calls collector
   - hooks/gemini_cli/     — reads Gemini CLI hook event, calls collector
   - hooks/kiro/           — reads Kiro hook event, calls collector
   - hooks/cursor_vscode/  — VS Code extension that calls collector
   Each adapter: parse IDE-specific event format → normalize → collector.track_*()

5. Update config generators (Phase 2 & 3)
   - Inject hook configuration into all generated configs
   - Include observal-collector install step in setup instructions

6. CLI commands
   - observal telemetry status (show: events received in last hour,
     last event timestamp, any errors)
   - observal telemetry test (send a test event, verify round-trip)

7. Data permission enforcement
   - Enterprise opt-out settings checked at collector level
     (strip fields before sending)
   - Developer opt-in settings for input_parameters and rag_context
     checked at ingestion API level
```

### Definition of Done
- Installing an MCP/agent from Observal includes hook setup automatically
- Tool calls made via Claude Code, Gemini CLI, Kiro, or Cursor are captured
- Events appear in ClickHouse within seconds
- `observal telemetry status` confirms data flow
- Opted-out fields are stripped before leaving the developer's machine

---

## Phase 5: Dashboards (Metrics & Observability)

**Goal:** Developers and admins can see how their MCP servers and agents are performing through the first Web UI views.

**Note:** This is where React development begins. Phases 1-4 are CLI + backend only.

### Deliverables
- React app skeleton with routing and auth (login page)
- Per-MCP dashboard: downloads, call volume, error rate, latency charts
- Per-Agent dashboard: acceptance rate, tool call chains, trace viewer
- Enterprise overview: total usage, top agents/MCPs, adoption trends
- Real-time updates (polling or SSE from the API)

### Technical Tasks

```
1. React app scaffolding
   - Vite + React + TypeScript
   - Tailwind CSS for styling
   - React Router for navigation
   - Auth context (login with API key or session token)
   - Layout: sidebar nav + main content area

2. API endpoints for dashboards
   - GET /api/v1/mcps/:id/metrics (downloads, calls, errors, latency
     — aggregated from ClickHouse)
   - GET /api/v1/agents/:id/metrics (acceptance rate, call chains,
     interaction counts)
   - GET /api/v1/agents/:id/traces (paginated trace list with filters)
   - GET /api/v1/agents/:id/traces/:trace_id (full trace detail)
   - GET /api/v1/overview/stats (enterprise-wide aggregates)
   - GET /api/v1/overview/top-agents
   - GET /api/v1/overview/top-mcps
   - GET /api/v1/overview/trends (time-series adoption data)

3. Dashboard views
   - MCP Dashboard:
     ├── Download count (total + over time chart)
     ├── Call volume (daily/weekly/monthly bar chart)
     ├── Error rate (% over time, breakdown by error type)
     └── Latency distribution (p50/p90/p99 line chart)
   
   - Agent Dashboard:
     ├── Code acceptance rate (% over time line chart)
     ├── Total interactions (daily/weekly/monthly)
     ├── Tool call efficiency (avg calls per interaction)
     ├── Trace explorer (table: timestamp, user action, score, expand for detail)
     └── Trace detail view (full chain: tool calls → reasoning → output → user action)
   
   - Enterprise Overview:
     ├── Summary cards (total MCPs, total agents, total users, total calls today)
     ├── Top 5 agents by acceptance rate
     ├── Top 5 MCPs by call volume
     ├── Adoption trend (new users/submissions over time)
     └── Health alerts (agents/MCPs with declining metrics)

4. Nginx config
   - Serve React app on port 80/443
   - Proxy /api/* to FastAPI backend
   - Add observal-web service to docker-compose.yml
```

### Definition of Done
- Web UI accessible at the Observal server URL
- Login works with existing API key / credentials
- MCP dashboard shows real data from ClickHouse
- Agent dashboard shows traces with acceptance rate
- Enterprise overview shows org-wide stats
- Charts update when new telemetry arrives

---

## Phase 6: Feedback

**Goal:** Users can rate and review MCP servers and agents. Developers see feedback on their listings.

**Can run in parallel with Phase 5** (different part of the codebase).

### Deliverables
- Star ratings (1-5) on listings via CLI and Web UI
- Free-text comments via CLI and Web UI
- Feedback visibility configurable by admin
- Developer portal: "My Feedback" view

### Technical Tasks

```
1. Database models
   - feedback (id, listing_id, listing_type, user_id, rating,
     comment, created_at)

2. API endpoints
   - POST /api/v1/feedback (submit rating + optional comment)
   - GET /api/v1/mcps/:id/feedback (list feedback for a listing)
   - GET /api/v1/agents/:id/feedback
   - GET /api/v1/me/feedback-received (developer's received feedback)

3. CLI commands
   - observal rate <listing-id> --stars 4 --comment "Great tool"
   - observal feedback <listing-id> (show feedback for a listing)

4. Web UI components
   - Star rating widget on listing detail page
   - Comment form
   - Feedback list (with admin visibility toggle)
   - "My Feedback" tab in developer portal

5. Admin setting
   - Enterprise config: feedback_visibility = "public" | "private"
   - Applied at the API query level
```

### Definition of Done
- User can rate and comment on any MCP/agent
- Feedback appears on listing detail (visibility per enterprise config)
- Developer can see all feedback on their listings
- Average rating shown on marketplace listing cards

---

## Phase 7: Eval Engine (SLM-as-a-Judge)

**Goal:** The SLM evaluates agent traces against the goal template and produces structured scorecards with actionable recommendations.

**This is the hardest phase.** Budget extra time for prompt engineering the judge.

### Deliverables
- SLM judge that evaluates agent traces against goal templates
- Scorecard generation with all 5 dimensions
- Live MCP access for factual grounding checks
- On-demand evaluation via CLI (`observal evaluate <agent-id>`)
- Scheduled evaluation (cron-based)
- Scorecard history in the Agent Dashboard
- Version comparison view

### Technical Tasks

```
1. SLM runtime setup
   - Add Ollama or vLLM service to docker-compose.yml (optional)
   - Abstraction layer: EvalModel interface with two implementations:
     ├── LocalSLM (calls Ollama/vLLM on localhost)
     └── OpenAIMini (calls OpenAI 4o-mini API)
   - Enterprise config: eval_model = "local" | "openai"

2. Judge agent implementation
   - Input assembler: pulls goal template + trace + MCP access configs
   - Prompt template for the judge (this is the core IP — iterate heavily):
     "Given this agent's goal template, evaluate the following trace.
      For each grounding_required section, use the provided MCP tools
      to verify claims. Score each dimension 0-10 with justification.
      Identify the primary bottleneck. Compare against baseline if provided."
   - MCP client: the judge can call the same MCP servers as the evaluated
     agent (read-only). Reuse the same MCP connection logic from the
     collector library.
   - Output parser: extract structured scorecard from judge response
     (use structured output / JSON mode)

3. Evaluation pipeline
   - Fetch all unevaluated traces for an agent from ClickHouse
   - For each trace:
     ├── Assemble judge input (goal + trace + MCP access)
     ├── Call SLM judge
     ├── Parse scorecard
     ├── Store in PostgreSQL (scorecards table)
     └── Update aggregate scores
   - Handle failures gracefully (retry, skip, log)

4. Database models
   - scorecards (id, agent_id, trace_id, version, overall_score,
     overall_grade, recommendations, bottleneck, evaluated_at)
   - scorecard_dimensions (scorecard_id, dimension, score, grade, notes)
   - eval_runs (id, agent_id, triggered_by, started_at, completed_at,
     traces_evaluated, status)

5. Scheduling
   - Configurable cron per agent (stored in enterprise config)
   - Background worker that runs evaluations on schedule
   - Use APScheduler or Celery with Redis (add Redis to docker-compose
     if needed, otherwise use PostgreSQL-backed task queue to keep
     stack simple)

6. CLI commands
   - observal evaluate <agent-id> [--version X.Y.Z] [--trace-id <id>]
   - observal scorecards <agent-id> (list recent scorecards)
   - observal scorecard <scorecard-id> (show full detail)

7. Web UI additions
   - Scorecard history table in Agent Dashboard
   - Scorecard detail view (dimension table + recommendations + bottleneck)
   - Dimension trend charts (score per dimension over time)
   - Version comparison: select two versions, see side-by-side scorecards
   - "Run Evaluation" button in Agent Dashboard
```

### Prompt Engineering the Judge (Critical)

The judge prompt is the core of Observal's value. Plan to spend significant time iterating on it. Approach:

```
1. Start with a baseline prompt that produces structured JSON output
2. Test against 10-20 real traces from a sample agent
3. Calibrate: are scores consistent? Does it catch hallucinations?
4. Iterate on dimension definitions until scoring is reliable
5. Add few-shot examples to the prompt for consistency
6. Test grounding verification: does the judge actually call MCPs
   and catch unverifiable claims?
7. Document the prompt template as versioned — changes to the judge
   prompt affect all future scorecards, so track it.
```

### Definition of Done
- `observal evaluate <agent-id>` produces scorecards for all traces
- Scorecards show all 5 dimensions with scores, grades, and notes
- Recommendations are actionable and specific
- Factual grounding checks actually call MCPs and flag unverifiable claims
- Scorecard history visible in Web UI
- Version comparison works
- Scheduled evaluation runs on configured cadence

---

## Phase 8: Web UI Completion

**Goal:** Full Web UI covering all features built in Phases 1-7.

**Can start in parallel with Phase 7** — most views are already built in Phase 5 and 6.

### Deliverables
- Marketplace / Registry browser (search, filter, listing detail pages)
- Config snippet display with copy button and setup instructions
- Admin panel (enterprise settings, approval queue, user management)
- Developer portal (my submissions, scorecards, feedback)
- Full auth flow (login page, session management, role-based nav)

### Technical Tasks

```
1. Marketplace views
   - Registry listing grid (cards with name, description, rating,
     downloads, category badge)
   - Search bar + filters (category, IDE support, type, rating)
   - Listing detail page:
     ├── Full metadata
     ├── Config snippets (tabbed by IDE) with copy button
     ├── Setup instructions
     ├── Feedback section (ratings + comments)
     └── Usage metrics summary (downloads, active users)

2. Admin panel
   - Approval queue (pending submissions with validation results)
   - Approve / reject with comments
   - Enterprise settings:
     ├── Custom schema fields management
     ├── Approval mode toggle (auto vs manual)
     ├── Feedback visibility toggle
     ├── Data redaction field toggles
     ├── Eval model selection (local SLM vs OpenAI)
     ├── Eval schedule configuration
     └── Category management
   - User management (list users, assign roles)

3. Developer portal
   - My Submissions (list with status badges)
   - Submission detail (metadata, validation results, edit button)
   - My Scorecards (aggregated view across all my agents)
   - My Feedback (all ratings/comments received)

4. Auth flow
   - Login page (API key or username/password for local auth)
   - SSO/SAML integration (stretch — add if time allows, otherwise Phase 9)
   - Role-based navigation (admin panel only visible to admins)
```

### Definition of Done
- All CLI functionality is also available via Web UI
- Non-technical stakeholders (admin, team leads) can use Observal without touching the CLI
- Marketplace is browsable with search and filters
- Admin can manage the entire platform from the web

---

## Parallel Work Tracks

With a 2-3 person team, here's how to split work:

```
                     Week 1-3    Week 4-7    Week 8-10   Week 11-14  Week 15-18  Week 19-22
                     ────────    ────────    ────────    ────────    ────────    ────────
Engineer 1 (backend) Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 7 ──────────►
Engineer 2 (backend) Phase 1 ──► Phase 2 ──► Phase 4 (hooks) ─────► Phase 7 ──────────►
Engineer 3 (frontend)            (helps backend) ──────► Phase 5 ──► Phase 6 ─► Phase 8 ►
```

Key parallelization:
- **Phase 4** (hooks) can be split: one person does the ingestion API + ClickHouse + collector library, the other builds the IDE-specific hook adapters.
- **Phase 5** (dashboards) can start as soon as Phase 4 has data flowing, and runs in parallel with backend work.
- **Phase 6** (feedback) is small and can be done by the frontend engineer.
- **Phase 7** (evals) needs both backend engineers — one builds the judge pipeline, the other does the scheduling + MCP access layer.
- **Phase 8** runs in parallel with Phase 7.

---

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| IDE/CLI hook APIs change or are undocumented | Hooks break, no telemetry | Start with Claude Code (best documented hooks). Build adapters as thin as possible. Budget time for reverse-engineering. |
| SLM judge produces inconsistent scores | Eval engine is unreliable | Invest heavily in prompt engineering. Use structured JSON output. Add few-shot examples. Build a calibration test suite. |
| 100% trace evaluation is too resource-intensive | Server overload for popular agents | Add a queue with backpressure. Monitor eval throughput. Have a "sampling mode" ready to enable if needed. |
| FastMCP-only support limits adoption | Teams using TypeScript MCP SDKs can't use Observal | Clearly communicate Python/FastMCP scope in v1. Plan TypeScript MCP SDK support as first v2 addition. |
| ClickHouse adds operational complexity | Hard to debug, unfamiliar to team | Use ClickHouse in append-only mode (simple). Avoid complex joins. Write good migration docs. Consider TimescaleDB (Postgres extension) as a simpler alternative if team prefers. |

---

## Post-v1 Roadmap (What Comes Next)

1. **TypeScript MCP SDK support** (expand beyond FastMCP/Python)
2. **SSO/SAML full integration** (replace basic auth)
3. **Security scan stage** in validation pipeline (secret detection, dep audit)
4. **SLM quality check stage** in validation pipeline (description quality scoring)
5. **Test execution stage** in validation pipeline (sandboxed test runner)
6. **Git webhook integration** (auto-detect new versions on push)
7. **Inline IDE feedback** (thumbs up/down captured via hooks)
8. **SLM fine-tuning pipeline** (automated training on enterprise data)
9. **Multi-tenancy / team namespaces** in the registry
10. **OTLP export** (ship Observal telemetry to external observability tools)