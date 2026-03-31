# Observal

A self-hosted MCP server and AI agent registry platform for enterprises. Observal gives engineering teams a centralized place to manage, validate, distribute, and observe internal MCP servers and AI agents across agentic IDEs and CLIs.

## Why Observal?

Teams building AI tooling with Cursor, Kiro, Claude Code, Gemini CLI, and VS Code face common challenges:

- **Distribution** — No central marketplace for internal MCP servers and agents.
- **Standardization** — No way to enforce uniform quality and documentation across submissions.
- **Observability** — No visibility into how tools perform in real developer workflows.
- **Improvement** — No data-driven way to identify bottlenecks (prompt quality, RAG relevance, tool call efficiency).
- **Feedback** — No portal for users to report issues or request improvements.

Observal solves all of these as a single, self-hosted platform.

## Features

- **MCP Server Registry** — Submit, validate, review, and distribute MCP servers via CLI.
- **Automated Validation** — 2-stage pipeline: clone & inspect + manifest validation.
- **Admin Review Workflow** — Approve or reject submissions with role-based access control.
- **Multi-IDE Config Generation** — One-click install configs for Cursor, VS Code, Kiro, Claude Code, Windsurf, and Gemini CLI.
- **CLI-First Design** — Full-featured CLI for submission, discovery, installation, and admin review.
- **Role-Based Access** — Admin, Developer, and User roles with API key authentication.
- **Download Tracking** — Track adoption of MCP servers across the organization.
- **Search & Filtering** — Find MCP servers by name, description, or category.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | Python, FastAPI, Uvicorn |
| Database | PostgreSQL 16 (primary), ClickHouse (telemetry) |
| ORM | SQLAlchemy (async) + AsyncPG |
| CLI | Python, Typer, Rich |
| Deployment | Docker Compose |
| Validation | Pydantic, GitPython |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Python 3.11+
- Git

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/BlazeUp-AI/Observal.git
cd Observal
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set secure values:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@observal-db:5432/observal
CLICKHOUSE_URL=clickhouse://observal-clickhouse:8123/observal
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-secure-password>
SECRET_KEY=<generate-a-random-key>
```

### 3. Start the services

```bash
cd docker
docker compose up --build -d
```

This starts:
- **observal-api** on `http://localhost:8000`
- **PostgreSQL** on port `5432`
- **ClickHouse** on port `8123`

### 4. Install the CLI

```bash
pip install -e .
```

### 5. Initialize (first-run setup)

```bash
observal init
```

This creates the admin account and saves your API key to `~/.observal/config.json`.

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

### Submitting an MCP Server

```bash
# Submit a Git repository for review
observal submit https://github.com/your-org/your-mcp-server.git
```

The CLI will analyze the repository and prompt you for metadata (name, version, category, supported IDEs, etc.).

### Discovering MCP Servers

```bash
# List all approved MCP servers
observal list

# Filter by category
observal list --category "code-generation"

# Search by name or description
observal list --search "database"

# Show full details of an MCP server
observal show <mcp-id>
```

### Installing an MCP Server

```bash
# Get the config snippet for your IDE
observal install <mcp-id> --ide cursor
observal install <mcp-id> --ide vscode
observal install <mcp-id> --ide claude_code
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

## Project Structure

```
Observal/
├── observal-server/          # FastAPI backend
│   ├── api/
│   │   ├── deps.py           # Auth & dependency injection
│   │   └── routes/           # API route handlers
│   ├── models/               # SQLAlchemy database models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Business logic (validation, config generation)
│   ├── main.py               # App entrypoint
│   └── config.py             # Settings
├── observal_cli/             # Typer CLI application
│   ├── main.py               # CLI commands
│   ├── client.py             # HTTP client wrapper
│   └── config.py             # CLI config management
├── docker/
│   ├── docker-compose.yml    # Full service stack
│   ├── Dockerfile.api        # API container
│   └── nginx.conf            # Reverse proxy config
├── tests/
│   └── test_phase_1_2.sh     # Integration test suite
├── docs/                     # Architecture and planning docs
├── .env.example              # Environment variable template
└── pyproject.toml            # CLI package config
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/init` | First-run admin setup |
| `GET` | `/api/v1/auth/whoami` | Current user info |
| `POST` | `/api/v1/mcps/analyze` | Analyze a Git repo |
| `POST` | `/api/v1/mcps/submit` | Submit an MCP server |
| `GET` | `/api/v1/mcps` | List MCP servers (with search/filter) |
| `GET` | `/api/v1/mcps/{id}` | Get MCP server details |
| `POST` | `/api/v1/mcps/{id}/install` | Get IDE config snippet |
| `GET` | `/api/v1/review` | List pending reviews (admin) |
| `POST` | `/api/v1/review/{id}/approve` | Approve submission (admin) |
| `POST` | `/api/v1/review/{id}/reject` | Reject submission (admin) |
| `GET` | `/health` | Health check |

## Roadmap

Observal is being developed in 8 phases:

- [x] **Phase 1** — Foundation (Auth, Docker stack, CLI skeleton)
- [x] **Phase 2** — MCP Registry (Submit, validate, review, install)
- [ ] **Phase 3** — Agent Registry
- [ ] **Phase 4** — Hooks & Telemetry Ingestion
- [ ] **Phase 5** — Dashboards
- [ ] **Phase 6** — Feedback Portal
- [ ] **Phase 7** — SLM Evaluation Engine
- [ ] **Phase 8** — Web UI

See [`development-plan.md`](development-plan.md) for the full roadmap.

## Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run the integration tests:
   ```bash
   bash tests/test_phase_1_2.sh
   ```
5. Commit your changes: `git commit -m "Add your feature"`
6. Push to your fork: `git push origin feature/your-feature`
7. Open a Pull Request

Please ensure your code:
- Follows existing project conventions
- Includes appropriate error handling
- Works with the Docker Compose stack

## License

This project is currently unlicensed. See the repository for updates.
