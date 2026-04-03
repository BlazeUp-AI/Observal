# Observal

A self-hosted MCP server and AI agent registry platform for enterprises. Observal gives engineering teams a centralized place to manage, validate, distribute, and observe internal MCP servers and AI agents across agentic IDEs and CLIs.

## Why Observal?

Teams building AI tooling with Cursor, Kiro, Claude Code, Gemini CLI, and VS Code face common challenges:

- No central marketplace for internal MCP servers and agents
- No way to enforce uniform quality and documentation across submissions
- No visibility into how tools perform in real developer workflows
- No data-driven way to identify bottlenecks (prompt quality, RAG relevance, tool call efficiency)
- No portal for users to report issues or request improvements

Observal solves all of these as a single, self-hosted platform.

## Features

- MCP Server Registry: Submit, validate, review, and distribute MCP servers via CLI
- Agent Registry: Create, manage, and distribute AI agents with bundled MCP configs
- Automated Validation: 2-stage pipeline (clone and inspect + manifest validation)
- Admin Review Workflow: Approve or reject submissions with role-based access control
- Multi-IDE Config Generation: One-click install configs for Cursor, VS Code, Kiro, Claude Code, Windsurf, and Gemini CLI
- Telemetry Ingestion: Collect tool call and agent interaction events into ClickHouse
- Dashboards and Metrics: Track downloads, latency, error rates, and acceptance rates
- Feedback Portal: Rate and review MCP servers and agents
- SLM Evaluation Engine: LLM-as-judge scoring with scorecards, version comparison, and bottleneck detection
- CLI-First Design: Full-featured CLI for every operation
- Role-Based Access: Admin, Developer, and User roles with API key authentication

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | Python, FastAPI, Uvicorn |
| Database | PostgreSQL 16 (primary), ClickHouse (telemetry) |
| ORM | SQLAlchemy (async) + AsyncPG |
| Web UI | Next.js, React, TypeScript, Tailwind CSS |
| CLI | Python, Typer, Rich |
| Eval Engine | AWS Bedrock / OpenAI-compatible LLMs |
| Dependency Management | uv |
| Deployment | Docker Compose |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.11+
- Node.js 20+ (for local web UI development)
- Git

## Getting Started

```bash
git clone https://github.com/BlazeUp-AI/Observal.git
cd Observal
cp .env.example .env
# edit .env with your values

cd docker
docker compose up --build -d
cd ..

uv tool install --editable .
observal init
```

This starts the API (http://localhost:8000), web UI (http://localhost:3000), PostgreSQL, and ClickHouse. The CLI is installed via `uv tool install` and `observal init` creates your admin account.

For detailed setup instructions, local development, eval engine configuration, and troubleshooting, see [SETUP.md](SETUP.md).

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | | PostgreSQL connection string using asyncpg |
| `CLICKHOUSE_URL` | Yes | | ClickHouse connection string |
| `POSTGRES_USER` | Yes | `postgres` | PostgreSQL user |
| `POSTGRES_PASSWORD` | Yes | | PostgreSQL password |
| `SECRET_KEY` | Yes | | Secret key for API key hashing |
| `CLICKHOUSE_USER` | No | `default` | ClickHouse user |
| `CLICKHOUSE_PASSWORD` | No | `clickhouse` | ClickHouse password |
| `EVAL_MODEL_URL` | No | | OpenAI-compatible endpoint for the eval engine |
| `EVAL_MODEL_API_KEY` | No | | API key for the eval model (empty for AWS credential chain) |
| `EVAL_MODEL_NAME` | No | | Model name (e.g. `us.anthropic.claude-3-5-haiku-20241022-v1:0`) |
| `EVAL_MODEL_PROVIDER` | No | | `bedrock`, `openai`, or empty for auto-detect |
| `AWS_ACCESS_KEY_ID` | No | | AWS credentials for Bedrock eval engine |
| `AWS_SECRET_ACCESS_KEY` | No | | AWS credentials for Bedrock eval engine |
| `AWS_SESSION_TOKEN` | No | | AWS session token (if using temporary credentials) |
| `AWS_REGION` | No | `us-east-1` | AWS region for Bedrock |

## Usage

### Authentication

```bash
# First-time setup (creates admin account)
observal init

# Login with an existing API key
observal login

# Check current user
observal whoami
```

### MCP Servers

#### Submitting

```bash
# Submit a Git repository for review
observal submit https://github.com/your-org/your-mcp-server.git
```

The CLI analyzes the repository and prompts you for metadata (name, version, category, supported IDEs, etc.).

#### Discovering

```bash
# List all approved MCP servers
observal list

# Filter by category
observal list --category "code-generation"

# Search by name or description
observal list --search "database"

# Show full details
observal show <mcp-id>
```

#### Installing

```bash
# Get the config snippet for your IDE
observal install <mcp-id> --ide cursor
observal install <mcp-id> --ide vscode
observal install <mcp-id> --ide claude_code
observal install <mcp-id> --ide kiro
observal install <mcp-id> --ide windsurf
observal install <mcp-id> --ide gemini_cli
```

### Agents

#### Creating

```bash
# Interactive agent creation
observal agent create
```

The CLI walks you through setting the agent name, version, description, system prompt, model config, supported IDEs, linked MCP servers, and goal template sections.

#### Discovering

```bash
# List all active agents
observal agent list

# Search agents
observal agent list --search "code review"

# Show full agent details
observal agent show <agent-id>
```

#### Installing

```bash
# Get bundled config (rules file + MCP configs) for your IDE
observal agent install <agent-id> --ide cursor
observal agent install <agent-id> --ide kiro
observal agent install <agent-id> --ide claude-code
observal agent install <agent-id> --ide gemini-cli
```

### Admin Review

```bash
# List pending submissions
observal review list

# View submission details
observal review show <review-id>

# Approve or reject
observal review approve <review-id>
observal review reject <review-id> --reason "Missing documentation"
```

### Telemetry

```bash
# Check telemetry data flow status
observal telemetry status

# Send a test telemetry event
observal telemetry test
```

### Dashboards and Metrics

```bash
# Enterprise overview stats
observal overview

# MCP server metrics (downloads, calls, error rate, latency percentiles)
observal metrics <mcp-id> --type mcp

# Agent metrics (interactions, downloads, acceptance rate, latency)
observal metrics <agent-id> --type agent
```

### Feedback

```bash
# Rate an MCP server (1-5 stars)
observal rate <mcp-id> --stars 5 --type mcp --comment "Works great"

# Rate an agent
observal rate <agent-id> --stars 4 --type agent

# View feedback for an MCP server or agent
observal feedback <listing-id> --type mcp
observal feedback <listing-id> --type agent
```

### Evaluation Engine

The eval engine uses an LLM-as-judge approach to score agent traces across multiple dimensions.

```bash
# Run evaluation on an agent's traces
observal eval run <agent-id>

# Run evaluation on a specific trace
observal eval run <agent-id> --trace <trace-id>

# List scorecards for an agent
observal eval scorecards <agent-id>

# Filter scorecards by version
observal eval scorecards <agent-id> --version "1.0.0"

# Show scorecard details (dimensions, grades, recommendations)
observal eval show <scorecard-id>

# Compare two agent versions
observal eval compare <agent-id> --a "1.0.0" --b "2.0.0"
```

### Admin Settings

```bash
# List enterprise settings
observal admin settings

# Set a setting
observal admin set <key> <value>

# List all users
observal admin users
```

## Web UI

The web UI is available at http://localhost:3000 after starting the Docker stack. It provides:

- Overview dashboard with stats, top MCPs, and top agents
- MCP server browsing, search, submission, and detail views with IDE config generation
- Agent browsing, creation, detail views, and evaluation dashboards
- Admin pages for review management, enterprise settings, and user management
- Feedback and ratings on MCP servers and agents

The frontend proxies all `/api/*` requests to the backend through Next.js rewrites, so no separate API URL configuration is needed in the browser.

Login with your API key at `/login`.

## API Endpoints

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/init` | First-run admin setup |
| `POST` | `/api/v1/auth/login` | Login with API key |
| `GET` | `/api/v1/auth/whoami` | Current user info |

### MCP Servers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/mcps/analyze` | Analyze a Git repo for metadata pre-fill |
| `POST` | `/api/v1/mcps/submit` | Submit an MCP server for review |
| `GET` | `/api/v1/mcps` | List approved MCP servers (supports `search`, `category` params) |
| `GET` | `/api/v1/mcps/{id}` | Get MCP server details |
| `POST` | `/api/v1/mcps/{id}/install` | Get IDE config snippet and record download |
| `DELETE` | `/api/v1/mcps/{id}` | Delete an MCP server |

### Agents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/agents` | Create an agent |
| `GET` | `/api/v1/agents` | List active agents (supports `search` param) |
| `GET` | `/api/v1/agents/{id}` | Get agent details |
| `PUT` | `/api/v1/agents/{id}` | Update an agent |
| `POST` | `/api/v1/agents/{id}/install` | Get IDE config snippet for agent |
| `DELETE` | `/api/v1/agents/{id}` | Delete an agent |

### Review (Admin)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/review` | List pending submissions |
| `GET` | `/api/v1/review/{id}` | Get submission details |
| `POST` | `/api/v1/review/{id}/approve` | Approve a submission |
| `POST` | `/api/v1/review/{id}/reject` | Reject a submission |

### Telemetry

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/telemetry/events` | Ingest tool call and agent interaction events |
| `GET` | `/api/v1/telemetry/status` | Check telemetry data flow status |

### Dashboards

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/mcps/{id}/metrics` | MCP server metrics (downloads, calls, latency, error rate) |
| `GET` | `/api/v1/agents/{id}/metrics` | Agent metrics (interactions, downloads, acceptance rate) |
| `GET` | `/api/v1/overview/stats` | Enterprise overview stats |
| `GET` | `/api/v1/overview/top-mcps` | Top MCP servers by downloads |
| `GET` | `/api/v1/overview/top-agents` | Top agents by interactions |
| `GET` | `/api/v1/overview/trends` | Usage trends over time |

### Feedback

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/feedback` | Submit a rating and optional comment |
| `GET` | `/api/v1/feedback/mcp/{id}` | Get feedback for an MCP server |
| `GET` | `/api/v1/feedback/agent/{id}` | Get feedback for an agent |
| `GET` | `/api/v1/feedback/me` | Get feedback on your own submissions |
| `GET` | `/api/v1/feedback/summary/{id}` | Get rating summary (average, count) |

### Evaluation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/eval/agents/{id}` | Run evaluation on agent traces |
| `GET` | `/api/v1/eval/agents/{id}/runs` | List eval runs for an agent |
| `GET` | `/api/v1/eval/agents/{id}/scorecards` | List scorecards (supports `version` param) |
| `GET` | `/api/v1/eval/scorecards/{id}` | Get scorecard details with dimensions |
| `GET` | `/api/v1/eval/agents/{id}/compare` | Compare two agent versions |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/admin/settings` | List enterprise settings |
| `GET` | `/api/v1/admin/settings/{key}` | Get a specific setting |
| `PUT` | `/api/v1/admin/settings/{key}` | Set a setting value |
| `DELETE` | `/api/v1/admin/settings/{key}` | Delete a setting |
| `GET` | `/api/v1/admin/users` | List all users |
| `POST` | `/api/v1/admin/users` | Create a new user |
| `PUT` | `/api/v1/admin/users/{id}/role` | Change a user's role |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |

## Project Structure

```
Observal/
├── observal-server/          # FastAPI backend
│   ├── api/
│   │   ├── deps.py           # Auth and dependency injection
│   │   └── routes/           # API route handlers
│   │       ├── auth.py       # Authentication
│   │       ├── mcp.py        # MCP server CRUD
│   │       ├── agent.py      # Agent CRUD
│   │       ├── review.py     # Admin review workflow
│   │       ├── telemetry.py  # Event ingestion
│   │       ├── dashboard.py  # Metrics and overview
│   │       ├── feedback.py   # Ratings and comments
│   │       ├── eval.py       # Evaluation engine
│   │       └── admin.py      # Settings and user management
│   ├── models/               # SQLAlchemy database models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Business logic
│   │   ├── validation.py     # MCP repo validation pipeline
│   │   ├── config_gen.py     # IDE config snippet generation
│   │   ├── clickhouse.py     # ClickHouse client and queries
│   │   └── eval_engine.py    # LLM-as-judge evaluation
│   ├── main.py               # App entrypoint
│   ├── config.py             # Settings
│   ├── pyproject.toml        # Server package config (uv)
│   └── uv.lock               # Server lockfile
├── observal-web/             # Next.js web UI
│   └── src/
│       ├── app/              # App Router pages
│       ├── components/       # Shared components
│       └── lib/              # API client, auth context
├── observal_cli/             # Typer CLI application
│   ├── main.py               # CLI commands
│   ├── client.py             # HTTP client wrapper
│   └── config.py             # CLI config management
├── docker/
│   ├── docker-compose.yml    # Full service stack
│   ├── Dockerfile.api        # API container (uses uv)
│   └── Dockerfile.web        # Web UI container
├── tests/
│   ├── test_phase_1_2.sh     # Auth and MCP integration tests
│   ├── test_phase_3_4.sh     # Agent and telemetry integration tests
│   ├── test_phase_5_6.sh     # Dashboard and feedback integration tests
│   └── test_phase_7_8.sh     # Eval and admin integration tests
├── docs/                     # Guides, test plans, and checkpoints
├── .env.example              # Environment variable template
├── pyproject.toml            # CLI package config (uv)
└── uv.lock                   # CLI lockfile
```

## Running Tests

The test suite is a set of bash scripts that run against a live Docker stack. Make sure the services are running first:

```bash
cd docker
docker compose up --build -d
cd ..

# Auth and MCP server tests
bash tests/test_phase_1_2.sh

# Agent and telemetry tests
bash tests/test_phase_3_4.sh

# Dashboard and feedback tests
bash tests/test_phase_5_6.sh

# Eval engine and admin tests
bash tests/test_phase_7_8.sh
```

## Contributing

Contributions are welcome. See the repository for contribution guidelines.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run the integration tests
5. Commit and push
6. Open a Pull Request

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
