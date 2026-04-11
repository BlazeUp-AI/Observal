<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/logo-light.svg">
  <img alt="Observal" src="docs/logo-light.svg" width="320">
</picture>

### Agent registry with built-in observability. Discover, distribute, and monitor AI coding agents.

<p>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/status-alpha-orange?style=flat-square" alt="Status">
  <a href="https://github.com/BlazeUp-AI/Observal/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/BlazeUp-AI/Observal/ci.yml?branch=main&style=flat-square&label=CI" alt="CI"></a>
</p>

---

Observal is a self-hosted agent registry and observability platform. Discover, publish, and pull complete AI coding agents bundled with their MCP servers, skills, hooks, prompts, and sandboxes. Every component emits telemetry into ClickHouse so you can measure what's actually working.

It works with Cursor, Kiro, Claude Code, Gemini CLI, VS Code, Codex CLI, and GitHub Copilot.

## Quick Start

```bash
git clone https://github.com/BlazeUp-AI/Observal.git
cd Observal
cp .env.example .env          # edit with your values

cd docker && docker compose up --build -d && cd ..
uv tool install --editable .
observal init                  # create admin account
```

Already have MCP servers in your IDE? Instrument them in one command:

```bash
observal scan                  # auto-detect, register, and instrument everything
observal pull <agent-id> --ide cursor  # install a complete agent
```

This detects MCP servers from your IDE config files, registers them with Observal, and wraps them with `observal-shim` for telemetry without breaking your existing setup. A timestamped backup is created automatically.

## The Problem

Teams building AI coding agents have no way to package and distribute complete agent configurations. Components (MCP servers, skills, hooks) are scattered across repos with no standard packaging. There's no visibility into agent performance in production, and no way to compare agent versions on real workflows.

- How do you ship a complete AI agent with all its dependencies?
- Which components actually improve productivity vs which ones add noise?
- How does version 2.0 of your agent compare to 1.0 on real developer workflows?
- Can you measure what's working before investing more in tooling?

Without answers, teams can't improve their agents. They guess, ship changes, and hope for the better.

## How It Works

Observal is a registry for AI agents. Each agent bundles MCP servers, skills, hooks, prompts, and sandboxes into a single installable package. Run `observal pull <agent-id>` to install a complete agent with all its components.

A transparent shim (`observal-shim` for stdio, `observal-proxy` for HTTP) intercepts traffic without modifying it, pairs requests with responses into spans, and streams them to ClickHouse. The shim is injected automatically when you install an agent or component - no code changes required. You can also run `observal scan` to automatically detect and instrument your existing IDE setup.

```
IDE  <-->  observal-shim  <-->  MCP Server / Sandbox
                |
                v (fire-and-forget)
          Observal API  -->  ClickHouse (traces, spans, scores)
                |
                v
          Eval Engine (LLM-as-judge)  -->  Scorecards
```

The eval engine runs on traces after the fact. It scores agent sessions across dimensions like tool selection quality, prompt effectiveness, and code correctness. Scorecards let you compare agent versions, identify bottlenecks, and track improvements over time.

## What It Covers

Observal manages 6 component types that agents bundle together:

| Registry Type | What It Is | What Observal Measures |
|--------------|-----------|----------------------|
| Agents | AI agent configurations that bundle components (MCPs, skills, hooks, prompts, sandboxes) | Interaction count, acceptance rate, tool call efficiency, version comparison |
| MCP Servers | Model Context Protocol servers that expose tools to agents | Call volume, latency, error rates, schema compliance, FastMCP validation |
| Skills | Portable instruction packages (SKILL.md) that agents load on demand | Activation frequency, error rate correlation, session duration impact |
| Hooks | Lifecycle callbacks that fire at specific points during agent sessions | Execution count, block rate, latency overhead |
| Prompts | Managed prompt templates with variable substitution | Render count, token expansion, downstream success rate |
| Sandbox Exec | Docker execution environments for code running and testing | CPU/memory/disk, exit codes, OOM rate, timeout rate |

Every type emits telemetry into ClickHouse. Every type gets metrics, feedback, and eval scores. Admin review controls visibility in the public registry, but you can use your own items and collect telemetry immediately, no approval needed.

## IDE Support

Config generation and telemetry collection work across all major agentic IDEs:

| IDE | MCP | Agents | Skills | Hooks | Sandbox Exec | Prompts | Native OTel |
|-----|:---:|:------:|:------:|:-----:|:------------:|:-------:|:-----------:|
| Claude Code | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Codex CLI | Yes | Yes | Yes | - | Yes | Yes | Yes |
| Gemini CLI | Yes | Yes | Yes | - | Yes | Yes | Yes |
| GitHub Copilot | - | - | Yes | - | - | Yes | Yes |
| Kiro IDE | Yes | Yes | Yes | Yes | Yes | Yes | - |
| Kiro CLI | Yes | Yes | Yes | Yes | Yes | Yes | - |
| Cursor | Yes | Yes | Yes | Yes | Yes | Yes | - |
| VS Code | Yes | Yes | - | - | Yes | Yes | - |

IDEs with **Native OTel** support send full distributed traces, user prompts, LLM token usage, and tool execution telemetry directly to Observal via OpenTelemetry. This is configured automatically when you run `observal install`. IDEs without native OTel support use the `observal-shim` transparent proxy for MCP tool call telemetry.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 16, React 19, Tailwind CSS 4, shadcn/ui, Recharts |
| Backend API | Python, FastAPI, Uvicorn |
| Database | PostgreSQL 16 (primary), ClickHouse (telemetry) |
| ORM | SQLAlchemy (async) + AsyncPG |
| CLI | Python, Typer, Rich |
| Eval Engine | AWS Bedrock / OpenAI-compatible LLMs |
| Background Jobs | arq + Redis |
| Real-time | GraphQL subscriptions (Strawberry + WebSocket) |
| Dependency Management | uv |
| Telemetry Pipeline | OpenTelemetry Collector |
| Deployment | Docker Compose (7 services) |

## Setup & Configuration

For detailed setup, eval engine configuration, environment variables, and troubleshooting, see [SETUP.md](SETUP.md).

<details>
<summary><strong>CLI Usage</strong></summary>

### Authentication

```bash
observal init          # first-time admin setup
observal login         # login with API key
observal whoami        # check current user
```

### Quick Start with Existing Setup

```bash
observal scan              # detect and instrument all IDE configs in current directory
observal scan --ide cursor # target specific IDE
observal scan --dry-run    # preview changes without modifying files
observal scan /path/to/project --yes  # non-interactive
```

### Agent Workflow

```bash
# Agent Workflow
observal pull <agent-id> --ide <ide>    # install complete agent
observal agent init <name>              # scaffold new agent
observal agent add mcp <name@version>   # add component
observal agent add skill <name>         # add skill
observal agent build                    # generate agent.yaml
observal agent test                     # run in sandbox
observal agent publish                  # submit to registry

# Component Sources
observal registry add-source <git-url>  # add component source
observal registry sync                  # trigger re-sync
```

### Registry Operations

All component types follow the same pattern. All commands accept either an ID or a name.

```bash
# MCP Servers (ID or name works for all commands)
observal submit <git-url>
observal list [--category <cat>] [--search <term>]
observal show <id-or-name>
observal install <id-or-name> --ide <ide>

# Agents
observal agent create
observal agent list [--search <term>]
observal agent show <id>
observal agent install <id> --ide <ide>

# Skills
observal skill submit <git-url-or-path>
observal skill list [--task-type <type>] [--target-agent <agent>]
observal skill install <id> --ide <ide>

# Hooks
observal hook submit
observal hook list [--event <event>] [--scope <scope>]
observal hook install <id> --ide <ide>

# Prompts
observal prompt submit [--from-file <path>]
observal prompt list [--category <cat>]
observal prompt render <id> --var key=value

# Sandboxes
observal sandbox submit
observal sandbox list [--runtime docker|lxc]
observal sandbox install <id> --ide <ide>
```

### Admin Review

All registry types go through a single review workflow:

```bash
observal review list [--type mcp|agent|skill|hook|prompt|sandbox]
observal review show <id>
observal review approve <id>
observal review reject <id> --reason "Missing documentation"
```

### Observability

```bash
# Telemetry status
observal telemetry status

# Metrics for any registry type
observal metrics <id> --type mcp
observal metrics <id> --type agent

# Enterprise overview
observal overview
```

### Evaluation

```bash
# Run eval on agent traces
observal eval run <agent-id>

# List and inspect scorecards
observal eval scorecards <agent-id> [--version "1.0.0"]
observal eval show <scorecard-id>

# Compare versions
observal eval compare <agent-id> --a "1.0.0" --b "2.0.0"
```

### Feedback

```bash
# Rate any registry item (1-5 stars)
observal rate <id> --stars 5 --type mcp --comment "Works great"

# View feedback
observal feedback <id> --type mcp
```

</details>

<details>
<summary><strong>API Endpoints</strong></summary>

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/init` | First-run admin setup |
| `POST` | `/api/v1/auth/login` | Login with API key |
| `GET` | `/api/v1/auth/whoami` | Current user info |

### Registry (per type: mcps, agents, skills, hooks, prompts, sandboxes)

All `{id}` parameters accept either a UUID or a name.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/{type}` | Submit / create |
| `GET` | `/api/v1/{type}` | List approved items |
| `GET` | `/api/v1/{type}/{id}` | Get details |
| `POST` | `/api/v1/{type}/{id}/install` | Get IDE config snippet |
| `DELETE` | `/api/v1/{type}/{id}` | Delete |
| `GET` | `/api/v1/{type}/{id}/metrics` | Metrics |
| `POST` | `/api/v1/agents/{id}/pull` | Pull agent (installs all components) |
| `GET` | `/api/v1/organizations` | List organizations |
| `POST` | `/api/v1/organizations` | Create organization |
| `GET` | `/api/v1/component-sources` | List component sources |
| `POST` | `/api/v1/component-sources` | Add component source |

### Scan

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/scan` | Bulk register items from IDE config scan |

### Review

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/review` | List pending submissions |
| `GET` | `/api/v1/review/{id}` | Submission details |
| `POST` | `/api/v1/review/{id}/approve` | Approve |
| `POST` | `/api/v1/review/{id}/reject` | Reject |

### Telemetry

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/telemetry/ingest` | Batch ingest traces, spans, scores |
| `POST` | `/api/v1/telemetry/events` | Legacy event ingestion |
| `GET` | `/api/v1/telemetry/status` | Data flow status |

### Evaluation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/eval/agents/{id}` | Run evaluation |
| `GET` | `/api/v1/eval/agents/{id}/scorecards` | List scorecards |
| `GET` | `/api/v1/eval/scorecards/{id}` | Scorecard details |
| `GET` | `/api/v1/eval/agents/{id}/compare` | Compare versions |

### Feedback

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/feedback` | Submit rating |
| `GET` | `/api/v1/feedback/{type}/{id}` | Get feedback |
| `GET` | `/api/v1/feedback/summary/{id}` | Rating summary |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/settings` | List settings |
| `PUT` | `/api/v1/admin/settings/{key}` | Set a value |
| `GET` | `/api/v1/admin/users` | List users |
| `POST` | `/api/v1/admin/users` | Create user |
| `PUT` | `/api/v1/admin/users/{id}/role` | Change role |

### Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/alerts` | List alert rules |
| `POST` | `/api/v1/alerts` | Create alert rule |
| `PATCH` | `/api/v1/alerts/{id}` | Update alert status |
| `DELETE` | `/api/v1/alerts/{id}` | Delete alert rule |

### GraphQL

| Endpoint | Description |
|----------|-------------|
| `/api/v1/graphql` | Traces, spans, scores, metrics (query + subscription) |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |

</details>

<details>
<summary><strong>Environment Variables</strong></summary>

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | | PostgreSQL connection string (asyncpg) |
| `CLICKHOUSE_URL` | Yes | | ClickHouse connection string |
| `POSTGRES_USER` | Yes | `postgres` | PostgreSQL user |
| `POSTGRES_PASSWORD` | Yes | | PostgreSQL password |
| `SECRET_KEY` | Yes | | Secret key for API key hashing |
| `CLICKHOUSE_USER` | No | `default` | ClickHouse user |
| `CLICKHOUSE_PASSWORD` | No | `clickhouse` | ClickHouse password |
| `EVAL_MODEL_URL` | No | | OpenAI-compatible endpoint for the eval engine |
| `EVAL_MODEL_API_KEY` | No | | API key for the eval model |
| `EVAL_MODEL_NAME` | No | | Model name (e.g. `us.anthropic.claude-3-5-haiku-20241022-v1:0`) |
| `EVAL_MODEL_PROVIDER` | No | | `bedrock`, `openai`, or empty for auto-detect |
| `AWS_ACCESS_KEY_ID` | No | | AWS credentials for Bedrock |
| `AWS_SECRET_ACCESS_KEY` | No | | AWS credentials for Bedrock |
| `AWS_SESSION_TOKEN` | No | | AWS session token (temporary credentials) |
| `AWS_REGION` | No | `us-east-1` | AWS region for Bedrock |

</details>

## Running Tests

```bash
make test      # quick (526 tests)
make test-v    # verbose
```

All tests mock external services. No Docker needed.

## Community

Have a question, idea, or want to share what you've built? Head to [GitHub Discussions](https://github.com/BlazeUp-AI/Observal/discussions). Please use Discussions for questions instead of opening issues, issues are reserved for bug reports and feature requests.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide. The short version:

1. Fork and clone
2. `make hooks` to install pre-commit hooks
3. Create a feature branch
4. Make changes, run `make lint` and `make test`
5. Open a PR

See [AGENTS.md](AGENTS.md) for internal codebase context useful when working with AI coding agents.

## License

Apache License 2.0. See [LICENSE](LICENSE).
