# Observal — Product Specification Document

**Version:** 1.0
**Date:** March 30, 2026
**Status:** Draft — Ready for Development

---

## 1. Overview

### 1.1 What is Observal?

Observal is a self-hosted platform for enterprises to manage the lifecycle of internal MCP servers and AI agents. It provides a centralized registry (marketplace), observability through IDE/CLI hooks, AI-powered evaluation of agent quality using an SLM-as-a-judge, and a feedback portal — purpose-built for engineering teams building AI tooling for agentic IDEs and CLIs.

### 1.2 Problem Statement

Engineering organizations are rapidly creating MCP servers and AI agents for internal use with tools like Cursor, Kiro, Claude Code, and Gemini CLI. They face five compounding challenges:

1. **Distribution & Adoption** — No central place to publish, discover, or install internal MCP servers and agents.
2. **Standardization** — No enforcement of uniform quality, naming, descriptions, or documentation across submissions.
3. **Observability** — No visibility into how MCP servers and agents perform in real developer workflows, including whether generated code is actually accepted.
4. **Iteration & Improvement** — No data-driven way to identify bottlenecks (prompt quality, RAG relevance, tool call efficiency) and improve agent performance over time.
5. **Feedback** — No portal for users to report issues, rate tools, or request improvements.

### 1.3 Why Not Build In-House?

Enterprises could build this internally, but it requires:

- A dedicated team to build and maintain the marketplace, hook integrations, and dashboards.
- Continuous updates as IDEs and CLIs evolve (new hook APIs, new tools, breaking changes).
- Significant R&D investment to train and manage an SLM that can evaluate agent traces against stated goals, verify factual grounding, and identify improvement opportunities.

Observal absorbs all of this complexity as a product.

### 1.4 Glossary

| Term | Definition |
|---|---|
| **Enterprise** | The organization that deploys Observal (our customer). |
| **MCP Server** | An AI tool built to the Model Context Protocol spec, consumed by agentic IDEs/CLIs. |
| **Agent** | A composite of Prompt + MCP servers + Model configuration, designed to perform a specific task. |
| **Developer** (publisher) | An engineer within the enterprise who creates and submits MCP servers or agents to the registry. |
| **User** (consumer) | An engineer within the enterprise who installs and uses MCP servers or agents in their daily workflow. |
| **Customer** | End-customers of the enterprise (not Observal's customer — the enterprise's customer). |
| **SLM** | Small Language Model, used as an automated judge for evaluating agent trace quality. |

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DEVELOPER WORKSTATIONS                       │
│                                                                     │
│   ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐      │
│   │  Cursor   │  │   Kiro   │  │Claude Code│  │  Gemini CLI  │      │
│   │  / VSCode │  │          │  │   (CLI)   │  │              │      │
│   └────┬─────┘  └────┬─────┘  └─────┬─────┘  └──────┬───────┘      │
│        │              │              │               │              │
│        └──────┬───────┴──────┬───────┴───────┬───────┘              │
│               │              │               │                      │
│        ┌──────▼──────────────▼───────────────▼──────┐               │
│        │       Observal Hook Scripts (per IDE/CLI)   │              │
│        │    Thin adapters → shared collector library  │              │
│        └─────────────────────┬───────────────────────┘              │
└──────────────────────────────┼──────────────────────────────────────┘
                               │ Real-time streaming (JSON over HTTPS)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     OBSERVAL SERVER (Docker)                         │
│                                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────────────┐  │
│  │  Ingestion API  │  │  Registry API   │  │    Web UI (React)    │  │
│  │  (telemetry)    │  │  (submit/browse)│  │                      │  │
│  └───────┬────────┘  └───────┬────────┘  └──────────────────────┘  │
│          │                   │                                      │
│  ┌───────▼───────────────────▼────────────────────────────────┐     │
│  │                   Python Backend API                        │     │
│  └───────┬──────────────┬─────────────────┬───────────────────┘     │
│          │              │                 │                          │
│  ┌───────▼──────┐ ┌────▼──────┐  ┌───────▼────────────────────┐    │
│  │  PostgreSQL   │ │ClickHouse │  │   SLM Evaluation Engine    │    │
│  │  (registry,   │ │(telemetry,│  │  ┌──────────────────────┐  │    │
│  │   auth,       │ │ time-     │  │  │ Custom SLM (self-    │  │    │
│  │   feedback)   │ │ series)   │  │  │ hosted, large        │  │    │
│  │              │ │           │  │  │ codebases)           │  │    │
│  └──────────────┘ └───────────┘  │  ├──────────────────────┤  │    │
│                                  │  │ OpenAI 4o-mini       │  │    │
│                                  │  │ (API, small          │  │    │
│                                  │  │ codebases)           │  │    │
│                                  │  └──────────────────────┘  │    │
│                                  └────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Deployment Model

- **Self-hosted only** via Docker Compose.
- Air-gapped friendly: all core functionality works without internet access (when using the self-hosted SLM).
- Optional outbound access to OpenAI API for enterprises choosing 4o-mini as their evaluation model.
- Single `docker-compose up` to start the full stack (API, frontend, PostgreSQL, ClickHouse, SLM runtime).

### 2.3 Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python (FastAPI) |
| Frontend | React |
| Primary Database | PostgreSQL (registry, auth, feedback, config) |
| Telemetry Store | ClickHouse (time-series telemetry, trace data) |
| Deployment | Docker Compose |
| SLM Runtime | Self-hosted model (Ollama or vLLM) or OpenAI 4o-mini API |
| Auth | SSO/SAML + local accounts (fallback) |

---

## 3. Data Collection Layer

### 3.1 Approach: IDE/CLI Hook Scripts

Observal collects telemetry via lightweight hook scripts installed in each supported IDE/CLI. These hooks tap into the lifecycle of MCP calls and agent interactions at the client side, providing full visibility into what the user experiences — including code acceptance.

**Architecture:**

```
IDE/CLI Hook Script (thin, per-platform adapter)
    ↓ captures: tool call, response, user action
    ↓
Observal Collector Library (shared core logic)
    ↓ formats telemetry, buffers, streams
    ↓
Observal Server Ingestion API (HTTPS endpoint)
```

- Hook scripts are minimal adapters specific to each IDE/CLI's hook API.
- The shared collector library (Python or Node package, depending on the IDE runtime) handles formatting, buffering, retry logic, and streaming.
- If the Observal server is temporarily unreachable, the collector buffers events locally and flushes when connectivity is restored.

### 3.2 Supported IDEs/CLIs (v1)

| IDE/CLI | Hook Mechanism | Notes |
|---|---|---|
| Cursor / VS Code family | VS Code Extension API | Single extension covers both. Listens to MCP call events, tool responses, and editor actions (accept/reject). |
| Kiro | Kiro hook system | AWS-built, agent-first IDE. Hook integration via Kiro's lifecycle hooks. |
| Claude Code | CLI hooks (pre/post tool use) | Built-in hook support. Hook script registered in Claude Code configuration. |
| Gemini CLI | CLI hook system | Hook integration via Gemini CLI's event callbacks. |

### 3.3 Telemetry Protocol

- **Format:** JSON envelope as the canonical format.
- **Transport:** Real-time streaming over HTTPS. Each event is shipped immediately as it occurs.
- **OTLP compatibility:** For IDEs/CLIs that natively support OpenTelemetry, Observal provides an OTLP-to-Observal adapter at the ingestion layer. Platforms that don't support OTLP (e.g. Kiro) post JSON directly.
- **Local buffer:** Events are buffered in-memory (with disk spillover) if the server is unreachable. Flushed on reconnection. No telemetry is lost.

### 3.4 Telemetry Schema

#### Per MCP Tool Call Event

```json
{
  "event_type": "mcp_tool_call",
  "timestamp": "ISO-8601",
  "session_id": "uuid",
  "ide_cli": "cursor | kiro | claude-code | gemini-cli",
  "ide_cli_version": "string",
  "hook_version": "string",
  "mcp_server_id": "registry-id",
  "tool_name": "string",
  "input_parameters": { },
  "response_payload": { },
  "latency_ms": 0,
  "status": "success | error",
  "error_type": "string | null",
  "error_message": "string | null"
}
```

#### Per Agent Interaction Event

```json
{
  "event_type": "agent_interaction",
  "timestamp": "ISO-8601",
  "session_id": "uuid",
  "ide_cli": "string",
  "agent_id": "registry-id",
  "model_used": "string",
  "token_count": { "input": 0, "output": 0 },
  "tool_call_chain": [
    {
      "mcp_server_id": "string",
      "tool_name": "string",
      "input_parameters": { },
      "response_payload": { },
      "latency_ms": 0,
      "status": "success | error"
    }
  ],
  "rag_context": [ ],
  "agent_reasoning": "string",
  "final_output": "string",
  "user_action": "accepted | rejected | edited | ignored",
  "time_to_action_ms": 0
}
```

#### Per Session Summary (aggregated at session end)

```json
{
  "event_type": "session_summary",
  "session_id": "uuid",
  "ide_cli": "string",
  "started_at": "ISO-8601",
  "ended_at": "ISO-8601",
  "total_mcp_calls": 0,
  "total_agent_interactions": 0,
  "acceptance_rate": 0.0,
  "error_rate": 0.0,
  "tools_used": ["string"]
}
```

### 3.5 Data Permission Model

Telemetry data is controlled at two levels:

1. **Enterprise-level (Admin):** Basic opt-out per field category. Admin can toggle off entire categories such as `input_parameters`, `response_payload`, `rag_context`, `agent_reasoning`, `final_output`. When a category is toggled off, those fields are stripped at the collector level before data leaves the developer's machine.

2. **Developer-level (publisher):** MCP/Agent developers can independently control whether `input_parameters` and `rag_context` are captured for their specific tool/agent. This is configured per listing in the registry. Developer restrictions are additive to enterprise restrictions (a developer cannot re-enable a field the enterprise has disabled).

---

## 4. Registry (Marketplace)

### 4.1 Overview

The registry is an internal marketplace where developers publish MCP servers and agents, and users discover and install them. It has two sub-registries sharing the same infrastructure:

- **MCP Registry** — individual MCP servers.
- **Agent Registry** — agents (composites of Prompt + MCP servers + Model configuration).

### 4.2 Submission Flow

Developers can submit via **CLI** (`observal submit <GIT_URL>`) or **Web UI** (form-based). Metadata (description, category, setup instructions, etc.) is entered manually via CLI prompts or the web form — not inferred from the repository.

```
Developer submits via CLI or Web UI
        │
        ▼
┌─ Stage 1: Clone & Inspect ──────────────────────────────────┐
│  Clone the repo. Detect type (MCP server vs Agent).          │
│  For Agents: verify referenced MCP servers exist in registry.│
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌─ Stage 2: Manifest Validation ──────────────────────────────┐
│  MCP: valid MCP manifest (tools, descriptions, schemas).     │
│  Agent: valid agent definition (prompt file, MCP refs,       │
│         model config).                                       │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌─ Stage 3: Security Scan ────────────────────────────────────┐
│  Scan for leaked secrets, known vulnerable dependencies,     │
│  malicious code patterns.                                    │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌─ Stage 4: Standards Check ──────────────────────────────────┐
│  Validate against Observal base schema + enterprise custom   │
│  required fields. Check naming conventions, description      │
│  format, required metadata completeness.                     │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌─ Stage 5: Test Execution ───────────────────────────────────┐
│  Run included tests and examples in a sandboxed              │
│  environment. Report pass/fail.                              │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌─ Stage 6: SLM Quality Check ───────────────────────────────┐
│  SLM evaluates description clarity, completeness, and        │
│  whether tool/agent descriptions will work well with LLMs.   │
│  Flags vague, misleading, or incomplete descriptions.        │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌─ Stage 7: Approval Gate (configurable per enterprise) ──────┐
│  Option A: Auto-approve if all checks pass.                  │
│  Option B: Queue for admin review. Admin is notified and     │
│            reviews in Web UI. Approves or rejects with       │
│            comments.                                         │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
                   Published to Marketplace
```

If any stage fails, the submission is rejected with a detailed report explaining what failed and how to fix it.

### 4.3 Listing Schema

**Observal Base Schema (required for all deployments):**

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | Yes | Unique within the enterprise registry |
| `version` | semver | Yes | e.g. 1.0.0 |
| `type` | enum | Yes | `mcp_server` or `agent` |
| `owner` | string | Yes | Developer or team name |
| `description` | text | Yes | Min 100 characters |
| `category` | enum | Yes | Enterprise-defined categories |
| `supported_ides` | array | Yes | e.g. ["cursor", "kiro", "claude-code", "gemini-cli"] |
| `setup_instructions` | text | Yes | How to configure and use |
| `changelog` | text | Yes | What changed in this version |
| `git_url` | url | Yes | Source repository |

**Agent-specific additional fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `prompt` | text | Yes | The agent's system prompt |
| `mcp_dependencies` | array | Yes | List of MCP server IDs this agent requires |
| `model_config` | object | Yes | Model name, parameters, token limits |
| `goal_template` | object | Yes | Structured goal with required output sections (see §5.2) |

**Enterprise Custom Fields:**

Enterprises can define additional required or optional fields on top of the base schema via the Admin settings. Examples: `compliance_tag`, `data_classification`, `team_slack_channel`, `review_cadence`.

### 4.4 Config File Generation

When a user clicks "Install" on a marketplace listing, Observal auto-generates ready-to-paste configuration snippets for all supported IDEs/CLIs:

- **Cursor / VS Code:** `.cursor/mcp.json` or `.vscode/mcp.json` snippet
- **Claude Code:** `.claude/settings.json` snippet or `claude mcp add` command
- **Kiro:** Kiro-compatible MCP configuration block
- **Gemini CLI:** Gemini CLI MCP configuration format

Each generated config includes the Observal hook integration so that telemetry collection is automatically enabled when the user installs the MCP/Agent.

Setup instructions are displayed alongside the config snippet.

### 4.5 Marketplace Metrics

The registry tracks for each listing:

- **Download count** — how many users have installed the config.
- **Active users** — unique users who have made at least one call in the last 7/30 days (derived from telemetry).
- **Call volume** — total MCP tool calls (from telemetry).
- **Average rating** — from user feedback (see §6).

---

## 5. SLM-as-a-Judge Evaluation Engine

### 5.1 Purpose

The evaluation engine is Observal's core differentiator. It uses a language model to judge agent performance by analyzing real production traces against the developer's stated goal, with live access to the same data sources the agent used. This enables detection of hallucinations, inefficient tool use, poor reasoning, and prompt weaknesses.

**Applies to: Agents only.** MCP servers are evaluated via basic metric dashboards (latency, error rate, call volume) — they are too simple to warrant SLM evaluation.

### 5.2 Goal Template

When registering an agent, the developer provides a **goal template** — a structured definition of what the agent should accomplish and what its output should contain. This is the anchor for all evaluation.

**Example Goal Template:**

```yaml
agent_goal:
  description: >
    Analyze any customer support case and produce a root cause analysis,
    find similar past incidents, recommend next steps, and triage to
    the appropriate component team.
  required_output_sections:
    - name: "Root Cause"
      description: "Identify the technical root cause of the incident"
      grounding_required: true
    - name: "Similar Incidents"
      description: "List 2-5 similar past incidents with IDs"
      grounding_required: true
    - name: "Next Steps"
      description: "Actionable recommendations for resolution"
      grounding_required: false
    - name: "Triaged Component"
      description: "The module/team this should be assigned to"
      grounding_required: true
```

The `grounding_required` flag tells the SLM judge to verify claims in that section against the MCP data sources.

### 5.3 Evaluation Inputs

For every agent trace, the SLM judge receives:

1. **The Goal Template** — what the agent should have accomplished.
2. **The Full Trace** — every MCP call made, what was retrieved, the agent's reasoning chain, and the final output.
3. **Live MCP Access** — the judge has read access to the same MCP servers the agent used, allowing it to independently verify claims (e.g. checking whether a referenced incident actually exists in Jira, whether a quoted threshold exists in documentation).

### 5.4 Evaluation Dimensions

| Dimension | Score Range | What It Measures |
|---|---|---|
| **Goal Completion** | 0-10 | Were all required output sections present and substantive? |
| **Tool Call Efficiency** | 0-10 | Did the agent make optimal use of its MCPs? Penalizes redundant, overlapping, or unnecessary calls. |
| **Tool Call Failures** | 0-10 | How many MCP calls failed? Were failures handled gracefully? |
| **Factual Grounding** | 0-10 | Are claims in the output actually supported by the data sources? (SLM cross-references via live MCP access.) |
| **Thought Process** | 0-10 | Is the reasoning chain logical, transparent, and traceable? |

**Overall Score:** Weighted average across dimensions (weights configurable by the developer per agent).

### 5.5 Evaluation Output (Scorecard)

Each evaluation produces a structured scorecard:

```
Agent: Incident Analyzer v2.3
Trace ID: abc-123-def
Evaluated: 2026-03-30T14:22:00Z

╔═══════════════════════╦═══════╦═══════╦════════════════════════════════╗
║ Dimension             ║ Score ║ Grade ║ Notes                          ║
╠═══════════════════════╬═══════╬═══════╬════════════════════════════════╣
║ Goal Completion       ║  9/10 ║   A   ║ All four outputs present.      ║
║ Tool Call Efficiency  ║  7/10 ║   B   ║ RAG MCP queried twice with     ║
║                       ║       ║       ║ overlapping queries.           ║
║ Tool Call Failures    ║ 10/10 ║  A+   ║ No failures.                   ║
║ Factual Grounding     ║  8/10 ║   A   ║ 6GB threshold claim not found  ║
║                       ║       ║       ║ in triage docs. Possible       ║
║                       ║       ║       ║ hallucination.                 ║
║ Thought Process       ║  8/10 ║   A   ║ Didn't explain how RAM setting ║
║                       ║       ║       ║ was identified as root cause.  ║
╠═══════════════════════╬═══════╬═══════╬════════════════════════════════╣
║ OVERALL               ║ 8.4   ║   A   ║                                ║
╚═══════════════════════╩═══════╩═══════╩════════════════════════════════╝

RECOMMENDATIONS:
1. Optimize RAG queries — the agent issued two queries to the incident
   RAG MCP with overlapping keywords. Consolidate into a single,
   broader query to reduce latency and token usage.
2. Source verification — the claim "UI should not have allowed config
   below 6GB" was not found in the triage documentation MCP. Either
   the agent hallucinated this threshold or it exists in a source the
   agent didn't consult. Add the system requirements doc as an
   additional MCP source, or adjust the prompt to only cite verified
   thresholds.
3. Reasoning transparency — the root cause identification step should
   include explicit reasoning: "Found Max RAM = 4GB in Jira field X,
   cross-referenced with known minimum of 6GB from doc Y."

BOTTLENECK IDENTIFIED:
→ Prompt issue: The agent's prompt does not instruct it to cite
  specific sources for threshold claims. Recommend adding: "For any
  numeric threshold or limit cited, include the source document and
  field where this value was found."

COMPARISON VS PREVIOUS VERSION (v2.2):
  Goal Completion:      9/10 → 9/10  (stable)
  Tool Call Efficiency: 6/10 → 7/10  (improved — reduced one redundant call)
  Tool Call Failures:   9/10 → 10/10 (improved — fixed timeout handling)
  Factual Grounding:    8/10 → 8/10  (stable — same hallucination pattern)
  Thought Process:      7/10 → 8/10  (improved — better reasoning chain)
  Overall:              7.8  → 8.4   (+0.6 improvement)
```

### 5.6 Dual Model Strategy

| Model | When Used | Deployment |
|---|---|---|
| **Custom SLM** (fine-tuned) | Enterprises with large legacy codebases. The model is trained on enterprise-specific terminology, system architecture, and domain patterns so it can meaningfully evaluate domain-specific agent outputs. | Self-hosted via Ollama or vLLM within the Docker deployment. Fully air-gapped compatible. |
| **OpenAI GPT-4o-mini** | Smaller codebases where a general-purpose model is sufficient. Cost-effective for high-volume evaluation. | API call to OpenAI. Requires outbound internet access. |

Enterprise Admin selects the model in Observal configuration. Can be set globally or per-agent.

### 5.7 Evaluation Schedule

- **Scheduled:** Configurable cadence (e.g. weekly reports). Evaluates all traces accumulated since last run.
- **On-demand:** Developer triggers evaluation for a specific agent from the Web UI or CLI (`observal evaluate <agent-id>`).
- **Sampling:** 100% of traces are evaluated. No sampling. Every trace gets a scorecard.

### 5.8 SLM Judge as an Agent

Architecturally, the SLM judge is itself an agent — it has a goal (evaluate this trace), access to MCPs (the same ones the evaluated agent uses, in read-only mode), and produces structured output (the scorecard). This means:

- The judge requires the same MCP credentials/access as the agent it evaluates. Enterprise Admin configures this at setup.
- The judge adds read-only load to MCP servers. For high-volume agents, this should be factored into MCP server capacity planning.
- **Who watches the watcher?** For v1, the judge is trusted. Developers review scorecards manually. Automated meta-evaluation is a v2 consideration.

---

## 6. Feedback Portal

### 6.1 Feedback Mechanisms

Users (consumers of MCP servers and agents) can provide feedback through:

1. **Star Ratings** — 1-5 stars on any MCP server or agent listing in the marketplace.
2. **Free-text Comments/Reviews** — Written feedback attached to a listing.

### 6.2 Visibility

Feedback visibility is **configurable per enterprise** by the Admin:

- **Public:** All users in the marketplace can see ratings and reviews.
- **Private:** Only the MCP/Agent developer and enterprise admins can see feedback.

### 6.3 Feedback Data Model

```json
{
  "feedback_id": "uuid",
  "listing_id": "registry-id",
  "listing_type": "mcp_server | agent",
  "user_id": "string",
  "rating": 1-5,
  "comment": "string | null",
  "created_at": "ISO-8601"
}
```

Stored in PostgreSQL. Aggregated ratings displayed on marketplace listings.

---

## 7. Web UI & Dashboard

### 7.1 Views

The Web UI is a React application serving five primary views:

#### 7.1.1 Registry / Marketplace

- Browse and search all published MCP servers and agents.
- Filter by: category, rating, supported IDE, owner/team, type (MCP vs Agent).
- Each listing shows: name, description, version, rating, download count, active users, supported IDEs.
- Detail page: full metadata, setup instructions, auto-generated config snippets (with copy/download), changelog, reviews.
- "Install" button generates IDE-specific config snippet.

#### 7.1.2 Per-MCP Server Dashboard

- **Downloads** over time.
- **Call volume** — total calls, calls per day/week/month.
- **Error rate** — percentage of failed calls, breakdown by error type.
- **Latency** — p50, p90, p99 latency distributions.
- **Active users** — unique users over time.
- No SLM evaluation (MCP servers are evaluated via metrics only).

#### 7.1.3 Per-Agent Dashboard

- **Scorecard History** — every SLM evaluation scorecard, sortable by date and score.
- **Dimension Trends** — line charts showing each evaluation dimension over time (goal completion, efficiency, grounding, etc.).
- **Trace Explorer** — browse individual agent traces, see the full tool call chain, reasoning, output, and user action (accepted/rejected/edited).
- **Version Comparison** — side-by-side scorecard comparison across agent versions.
- **Code Acceptance Rate** — percentage of agent outputs accepted by users over time.
- **Bottleneck Summary** — aggregated SLM recommendations (e.g. "Prompt issue flagged in 12 of last 50 traces").

#### 7.1.4 Enterprise-Wide Overview

- **Total usage** — aggregate MCP calls and agent interactions across the org.
- **Top agents** — ranked by usage, acceptance rate, or SLM score.
- **Top MCP servers** — ranked by call volume, error rate, or downloads.
- **Adoption trends** — new users, new submissions, growth over time.
- **Health overview** — agents/MCPs with declining scores or rising error rates.

#### 7.1.5 Developer Portal

- **My Submissions** — all MCP servers and agents I've published, with status (pending, approved, rejected).
- **My Scorecards** — latest evaluation results for my agents.
- **My Feedback** — reviews and ratings received on my listings.
- **Submission Management** — edit metadata, update versions, configure telemetry permissions (input_parameters, rag_context opt-in/out).

---

## 8. Authentication & Authorization

### 8.1 Authentication

- **Primary:** SSO/SAML integration with the enterprise identity provider.
- **Fallback:** Local accounts with email/password for environments where SSO is not available or during initial setup.
- Session management via JWT tokens.

### 8.2 Roles

| Role | Permissions |
|---|---|
| **Admin** | Full access. Configure enterprise settings (custom schema fields, approval workflows, feedback visibility, data redaction rules, SLM model choice). Manage users and roles. Review and approve/reject submissions. Access all dashboards. |
| **Developer** (publisher) | Submit MCP servers and agents. Manage own listings (edit, update, configure telemetry permissions). View own scorecards and feedback. Browse marketplace. |
| **User** (consumer) | Browse marketplace. Install MCP servers and agents. Leave ratings and reviews. View own usage data. |

A single person can hold multiple roles (e.g. a developer is typically also a user). Roles are assigned by Admins.

---

## 9. CLI Reference

The Observal CLI (`observal`) is the developer-facing command-line tool.

| Command | Description |
|---|---|
| `observal submit <GIT_URL>` | Submit an MCP server or agent for review. Launches interactive prompts for metadata entry. |
| `observal status <submission-id>` | Check the status of a submission (pending, validating, approved, rejected). |
| `observal evaluate <agent-id>` | Trigger on-demand SLM evaluation for an agent. |
| `observal list [--type mcp\|agent] [--mine]` | List registry entries. Filter by type or owned submissions. |
| `observal config <listing-id> [--ide cursor\|kiro\|claude-code\|gemini-cli]` | Generate and print the config snippet for a specific IDE/CLI. |
| `observal login` | Authenticate against the Observal server (SSO or local). |

---

## 10. Data Storage

### 10.1 PostgreSQL

Stores:
- Registry listings (metadata, versions, approval status)
- User accounts and roles
- Feedback (ratings, comments)
- Enterprise configuration (custom fields, approval rules, redaction settings)
- Agent goal templates
- SLM scorecards (structured results)

### 10.2 ClickHouse

Stores:
- All telemetry events (MCP tool calls, agent interactions, session summaries)
- High-volume, append-only, optimized for time-range queries and aggregations
- Powers all dashboards and trend charts
- Retention policy configurable by enterprise Admin

---

## 11. Docker Compose Services

```yaml
services:
  observal-api:        # Python FastAPI backend
  observal-web:        # React frontend (served via nginx)
  observal-db:         # PostgreSQL
  observal-clickhouse: # ClickHouse
  observal-slm:        # SLM runtime (Ollama/vLLM) — optional, for self-hosted model
```

Single command deployment: `docker compose up -d`

Environment configuration via `.env` file covering: database credentials, SSO/SAML settings, SLM model choice (local vs OpenAI), OpenAI API key (if applicable), telemetry retention days.

---

## 12. v1 Scope Summary

### In Scope

- Self-hosted Docker deployment
- MCP Registry + Agent Registry with 5-stage validation pipeline
- Configurable approval gate (auto vs manual)
- Base schema + enterprise custom fields
- CLI (`observal`) + Web UI for submission and browsing
- Auto-generated config snippets for Cursor, Kiro, Claude Code, Gemini CLI
- IDE/CLI hook scripts for all four supported platforms
- Real-time telemetry streaming with JSON envelope format
- Enterprise-level field opt-out + developer-level input/RAG opt-in
- Per-MCP metric dashboards (downloads, calls, errors, latency)
- Per-Agent dashboards with SLM scorecards, trends, trace explorer
- Enterprise-wide overview dashboard
- Developer portal (my submissions, scorecards, feedback)
- SLM-as-a-judge evaluation (100% trace evaluation, live MCP access)
- Dual model support (self-hosted SLM + OpenAI 4o-mini)
- Scheduled + on-demand evaluation
- Star ratings + free-text reviews with configurable visibility
- SSO/SAML + local auth with three roles (Admin, Developer, User)

### Out of Scope (v2 Candidates)

- OTLP native export from Observal to external observability tools
- Automated version detection from Git (webhook-triggered updates)
- Inline IDE feedback (thumbs up/down in editor)
- Bug reports with trace attachment
- Feature request portal
- Meta-evaluation (who watches the watcher)
- Multi-instance federation (shared marketplace across enterprise instances)
- SLM fine-tuning pipeline within Observal (v1 assumes pre-trained model is provided)

---

## 13. Open Questions

1. **SLM training pipeline:** For the custom SLM, does Observal provide tooling to fine-tune on enterprise data, or does the enterprise bring a pre-trained model? (Recommendation: v1 ships with a base model and an optional fine-tuning guide; automated pipeline in v2.)

2. **Hook script distribution:** How are hook scripts installed on developer machines? Options: npm/pip package, included in the config snippet, or a separate `observal install-hooks` CLI command.

3. **Versioning and updates:** When a developer pushes a new version to Git, how does the registry listing get updated? Currently requires re-submission. Consider Git webhook integration for v2.

4. **Rate limiting on SLM:** Evaluating 100% of traces with live MCP access is resource-intensive. For high-volume agents (thousands of traces/day), should there be a configurable throttle or queue?

5. **Multi-tenancy:** If an enterprise has multiple teams that shouldn't see each other's listings, does the registry need namespace/team scoping?