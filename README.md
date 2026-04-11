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
  <a href="https://github.com/BlazeUp-AI/Observal/stargazers"><img src="https://img.shields.io/github/stars/BlazeUp-AI/Observal?style=flat-square" alt="Stars"></a>
</p>

> If you find Observal useful, please consider giving it a star. It helps others discover the project and keeps development going.

---

Observal is a **self-hosted agent registry and observability platform**. Think Docker Hub for AI agents. Discover, publish, and pull complete AI coding agents bundled with their MCP servers, skills, hooks, prompts, and sandboxes. Every component emits telemetry into ClickHouse so you can measure what's actually working.

Works with **Cursor**, **Kiro**, **Claude Code**, **Gemini CLI**, **VS Code**, **Codex CLI**, and **GitHub Copilot**.

## Quick Start

```bash
git clone https://github.com/BlazeUp-AI/Observal.git
cd Observal
cp .env.example .env          # edit with your values

cd docker && docker compose up --build -d && cd ..
uv tool install --editable .
observal auth init             # create admin account
```

Already have MCP servers in your IDE? Instrument them in one command:

```bash
observal scan                  # auto-detect, register, and instrument everything
observal pull <agent> --ide cursor  # install a complete agent
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

Observal is a registry for AI agents. Each agent bundles MCP servers, skills, hooks, prompts, and sandboxes into a single installable package. Run `observal pull <agent>` to install a complete agent with all its components.

A transparent shim (`observal-shim` for stdio, `observal-proxy` for HTTP) intercepts traffic without modifying it, pairs requests with responses into spans, and streams them to ClickHouse. The shim is injected automatically when you install an agent or component — no code changes required. You can also run `observal scan` to automatically detect and instrument your existing IDE setup.

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
| **Agents** | AI agent configurations that bundle components | Interaction count, acceptance rate, tool call efficiency, version comparison |
| **MCP Servers** | Model Context Protocol servers that expose tools to agents | Call volume, latency, error rates, schema compliance |
| **Skills** | Portable instruction packages (SKILL.md) that agents load on demand | Activation frequency, error rate correlation, session duration impact |
| **Hooks** | Lifecycle callbacks that fire at specific points during agent sessions | Execution count, block rate, latency overhead |
| **Prompts** | Managed prompt templates with variable substitution | Render count, token expansion, downstream success rate |
| **Sandbox Exec** | Docker execution environments for code running and testing | CPU/memory/disk, exit codes, OOM rate, timeout rate |

Every type emits telemetry into ClickHouse. Every type gets metrics, feedback, and eval scores. Admin review controls visibility in the public registry, but you can use your own items and collect telemetry immediately — no approval needed.

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

## CLI Reference

The CLI is organized into command groups. Run `observal --help` or `observal <group> --help` for full details.

### Primary Workflows

```bash
observal pull <agent> --ide <ide>    # install a complete agent with all dependencies
observal scan [--ide <ide>]          # detect and instrument existing IDE configs
observal use <git-url|path>          # swap IDE configs to a git-hosted profile
observal profile                     # show active profile and backup info
```

### Authentication (`observal auth`)

```bash
observal auth init             # first-time setup (connect to team or create admin)
observal auth login             # login with API key
observal auth logout            # clear saved credentials
observal auth whoami            # show current user
observal auth status            # check server connectivity and health
```

### Component Registry (`observal registry`)

All 5 component types live under `observal registry <type>`. Each type supports the same core commands:

```bash
# MCP Servers
observal registry mcp submit <git-url>
observal registry mcp list [--category <cat>] [--search <term>]
observal registry mcp show <id-or-name>
observal registry mcp install <id-or-name> --ide <ide>
observal registry mcp delete <id-or-name>

# Skills
observal registry skill submit [--from-file <path>]
observal registry skill list [--task-type <type>] [--target-agent <agent>]
observal registry skill show <id>
observal registry skill install <id> --ide <ide>
observal registry skill delete <id>

# Hooks
observal registry hook submit [--from-file <path>]
observal registry hook list [--event <event>] [--scope <scope>]
observal registry hook show <id>
observal registry hook install <id> --ide <ide>
observal registry hook delete <id>

# Prompts
observal registry prompt submit [--from-file <path>]
observal registry prompt list [--category <cat>]
observal registry prompt show <id>
observal registry prompt render <id> --var key=value
observal registry prompt install <id> --ide <ide>
observal registry prompt delete <id>

# Sandboxes
observal registry sandbox submit [--from-file <path>]
observal registry sandbox list [--runtime docker|lxc]
observal registry sandbox show <id>
observal registry sandbox install <id> --ide <ide>
observal registry sandbox delete <id>
```

### Agent Authoring (`observal agent`)

```bash
# Browse and manage agents
observal agent create              # interactive agent creation
observal agent list [--search <term>]
observal agent show <id>
observal agent install <id> --ide <ide>
observal agent delete <id>

# Local YAML workflow
observal agent init                # scaffold observal-agent.yaml
observal agent add <type> <id>     # add component (mcp, skill, hook, prompt, sandbox)
observal agent build               # validate against server (dry-run)
observal agent publish             # submit to registry
```

### Observability (`observal ops`)

```bash
observal ops overview              # enterprise dashboard stats
observal ops metrics <id> [--type mcp|agent] [--watch]
observal ops top [--type mcp|agent]
observal ops traces [--type <type>] [--mcp <id>] [--agent <id>]
observal ops spans <trace-id>
observal ops rate <id> --stars 5 [--type mcp|agent] [--comment "..."]
observal ops feedback <id> [--type mcp|agent]
observal ops telemetry status
observal ops telemetry test
```

### Admin (`observal admin`)

```bash
# Settings and users
observal admin settings
observal admin set <key> <value>
observal admin users

# Review workflow
observal admin review list
observal admin review show <id>
observal admin review approve <id>
observal admin review reject <id> --reason "..."

# Evaluation engine
observal admin eval run <agent-id> [--trace <trace-id>]
observal admin eval scorecards <agent-id> [--version "1.0.0"]
observal admin eval show <scorecard-id>
observal admin eval compare <agent-id> --a "1.0.0" --b "2.0.0"
observal admin eval aggregate <agent-id> [--window 50]

# Penalty and weight tuning
observal admin penalties
observal admin penalty-set <name> [--amount 10] [--active]
observal admin weights
observal admin weight-set <dimension> <weight>
```

### Configuration (`observal config`)

```bash
observal config show               # show current config
observal config set <key> <value>  # set a config value
observal config path               # show config file path
observal config alias <name> <id>  # create @alias for an ID
observal config aliases            # list all aliases
```

### Self-Management (`observal self`)

```bash
observal self upgrade              # upgrade CLI to latest version
observal self downgrade            # downgrade to previous version
```

### Diagnostics (`observal doctor`)

```bash
observal doctor [--ide <ide>] [--fix]  # diagnose IDE settings compatibility
```

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
| `GET` | `/api/v1/eval/agents/{id}/aggregate` | Aggregate scoring stats |

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
| `GET` | `/api/v1/admin/penalties` | List penalty catalog |
| `PUT` | `/api/v1/admin/penalties/{id}` | Modify penalty |
| `GET` | `/api/v1/admin/weights` | Get dimension weights |
| `PUT` | `/api/v1/admin/weights` | Set dimension weights |

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

Have a question, idea, or want to share what you've built? Head to [GitHub Discussions](https://github.com/BlazeUp-AI/Observal/discussions). Please use Discussions for questions instead of opening issues — issues are reserved for bug reports and feature requests.

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

## Star History

If you find Observal useful, please star the repo — it helps others discover the project and motivates continued development.

<a href="https://www.star-history.com/?repos=BlazeUp-AI%2FObserval&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=BlazeUp-AI/Observal&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=BlazeUp-AI/Observal&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=BlazeUp-AI/Observal&type=date&legend=top-left" />
 </picture>
</a>
