<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/logo-light.svg">
  <img alt="Observal" src="docs/logo-light.svg" width="320">
</picture>

### Discover, share, and monitor AI coding agents with full observability built in.

<p>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/status-alpha-orange?style=flat-square" alt="Status">
  <a href="https://github.com/BlazeUp-AI/Observal/stargazers"><img src="https://img.shields.io/github/stars/BlazeUp-AI/Observal?style=flat-square" alt="Stars"></a>
</p>

> If you find Observal useful, please consider giving it a star. It helps others discover the project and keeps development going.

---

Observal is a **self-hosted AI agent registry with built-in observability**. Think Docker Hub, but for AI coding agents.

Browse agents created by others, publish your own, and pull complete agent configurations — all defined in a portable YAML format that templates out to **Claude Code**, **Kiro CLI**, **Cursor**, **Gemini CLI**, and more. Every agent bundles its MCP servers, skills, hooks, prompts, and sandboxes into a single installable package. One command to install, zero manual config.

Every interaction generates traces, spans, and sessions that flow into a telemetry pipeline. The built-in eval engine scores agent sessions so you can measure performance and make your agents better over time.

## Documentation

**Full docs live at [observal.gitbook.io](https://observal.gitbook.io/observal)** (sourced from [`/docs`](docs/) in this repo).

| Start here | Go to |
| --- | --- |
| 5-minute install and first trace | [Quickstart](docs/getting-started/quickstart.md) |
| Understand the data model | [Core Concepts](docs/getting-started/core-concepts.md) |
| Instrument your existing MCP servers | [Observe MCP traffic](docs/use-cases/observe-mcp-traffic.md) |
| Run Observal on your infrastructure | [Self-Hosting](docs/self-hosting/README.md) |
| Look up a CLI command | [CLI Reference](docs/cli/README.md) |

See [CHANGELOG.md](CHANGELOG.md) for recent updates.

## Quick start

**Install the CLI** (standalone binary, no Python required):

```bash
curl -fsSL https://raw.githubusercontent.com/BlazeUp-AI/Observal/main/install.sh | bash
```

Or install via Python: `uv tool install observal-cli` / `pipx install observal-cli` / `pip install --user observal-cli`. See [Installation](docs/getting-started/installation.md) for details.

**Start the server:**

```bash
curl -fsSL https://raw.githubusercontent.com/BlazeUp-AI/Observal/main/install-server.sh | bash
```

Or manually:

```bash
git clone https://github.com/BlazeUp-AI/Observal.git
cd Observal
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build -d
```

**Log in:**

```bash
observal auth login            # auto-creates admin on fresh server
```

Eight services start (API, web UI, Postgres, ClickHouse, Redis, worker, OTEL collector, Grafana). Full walkthrough in [Quickstart](docs/getting-started/quickstart.md); operator guide in [Self-Hosting](docs/self-hosting/docker-compose.md).

Already have MCP servers in your IDE? Discover and instrument them:

```bash
observal scan                                # discover what's installed across your IDEs
observal doctor patch --all --all-ides       # instrument everything (hooks + shims + OTel)
observal pull <agent> --ide cursor           # install a complete agent
```

`scan` is read-only -- it shows what you have without modifying anything. `doctor patch` does the actual instrumentation: wrapping MCP servers with `observal-shim` for telemetry, installing hooks, and configuring OTel export. A timestamped backup is created automatically before any file is modified.

## Supported IDEs

| IDE | Support |
| --- | --- |
| Claude Code | Full — skills, hooks, MCP, rules, OTLP telemetry |
| Kiro CLI | Full — superpowers, hooks, MCP, steering files, OTLP telemetry |
| Gemini CLI | Native OTEL + shim telemetry |
| Codex CLI | Native OTEL + shim telemetry |
| GitHub Copilot | Shim telemetry |
| OpenCode | Shim telemetry |
| Cursor | MCP + shim telemetry |

Compatibility matrix and per-IDE setup: [Integrations](docs/integrations/README.md).

## Tech stack

| Component | Technology |
| --- | --- |
| Frontend | Next.js 16, React 19, Tailwind CSS 4, shadcn/ui, Recharts |
| Backend | Python 3.11+, FastAPI, Strawberry GraphQL, Uvicorn |
| Databases | PostgreSQL 16 (registry), ClickHouse (telemetry) |
| Queue | Redis + arq |
| CLI | Python, Typer, Rich |
| Eval engine | AWS Bedrock / OpenAI-compatible LLMs |
| Telemetry | OpenTelemetry Collector |
| Deployment | Docker Compose (8 services) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version:

1. Fork and clone
2. `make hooks` to install pre-commit hooks
3. Create a feature branch
4. Run `make lint` and `make test`
5. Open a PR

See [AGENTS.md](AGENTS.md) for internal codebase context.

## Running tests

```bash
make test      # quick
make test-v    # verbose
```

All tests mock external services. No Docker needed.

## ❓ FAQ

### General

**What is Observal?**
Observal is a self-hosted AI agent registry with built-in observability — think Docker Hub, but for AI coding agents. Browse, publish, and pull complete agent configurations that template out to Claude Code, Kiro CLI, Cursor, Gemini CLI, and more.

**How is Observal different from other agent registries?**
Every agent bundles its MCP servers, skills, hooks, prompts, and sandboxes into a single installable package. Every interaction generates traces, spans, and sessions with a built-in eval engine to measure and improve agent performance over time.

### Setup & Configuration

**What are the system requirements?**
- Python 3.11+ (for the Python CLI)
- Docker & Docker Compose (for the server)
- 8GB+ RAM recommended for running all eight services locally

**What services run when I start the server?**
Eight services start: API, web UI, Postgres, ClickHouse, Redis, worker, OTEL collector, and Grafana. See [Self-Hosting](docs/self-hosting/docker-compose.md) for the operator guide.

**Can I use Observal without Docker?**
The CLI is a standalone binary (no Python required). The server currently requires Docker Compose for the full telemetry stack.

### Usage

**How do I instrument my existing MCP servers?**
Run `observal scan` to discover what is installed across your IDEs, then `observal doctor patch --all --all-ides` to instrument everything with hooks, shims, and OpenTelemetry.

**What agent IDEs are supported?**
Claude Code, Kiro CLI, Cursor, Gemini CLI, and more. Pull complete agent configurations with `observal pull <agent> --ide <ide-name>`.

**How does the eval engine work?**
Every agent session generates traces and spans that flow into the telemetry pipeline. The built-in eval engine scores sessions so you can measure performance and iteratively improve your agents.

### Troubleshooting

**Server services fail to start**
Check that Docker and Docker Compose are running. Verify port availability (the stack uses multiple ports). Run `docker compose -f docker/docker-compose.yml ps` to check service status.

**CLI commands fail with authentication errors**
Run `observal auth login` to authenticate. On a fresh server this auto-creates an admin account. See [CLI Reference](docs/cli/README.md) for auth subcommands.

**No traces appearing in Grafana**
Ensure the OTEL collector is running and your IDE agents are instrumented with `observal doctor patch`. Check the collector logs with `docker compose -f docker/docker-compose.yml logs otel-collector`.



## ❓ FAQ

### General

**What is Observal?**
Observal is a self-hosted AI agent registry with built-in observability — think Docker Hub, but for AI coding agents. Browse, publish, and pull complete agent configurations that template out to Claude Code, Kiro CLI, Cursor, Gemini CLI, and more.

**How is Observal different from other agent registries?**
Every agent bundles its MCP servers, skills, hooks, prompts, and sandboxes into a single installable package. Every interaction generates traces, spans, and sessions with a built-in eval engine to measure and improve agent performance over time.

### Setup & Configuration

**What are the system requirements?**
- Python 3.11+ (for the Python CLI)
- Docker & Docker Compose (for the server)
- 8GB+ RAM recommended for running all eight services locally

**What services run when I start the server?**
Eight services start: API, web UI, Postgres, ClickHouse, Redis, worker, OTEL collector, and Grafana. See [Self-Hosting](docs/self-hosting/docker-compose.md) for the operator guide.

**Can I use Observal without Docker?**
The CLI is a standalone binary (no Python required). The server currently requires Docker Compose for the full telemetry stack.

### Usage

**How do I instrument my existing MCP servers?**
Run `observal scan` to discover what is installed across your IDEs, then `observal doctor patch --all --all-ides` to instrument everything with hooks, shims, and OpenTelemetry.

**What agent IDEs are supported?**
Claude Code, Kiro CLI, Cursor, Gemini CLI, and more. Pull complete agent configurations with `observal pull <agent> --ide <ide-name>`.

**How does the eval engine work?**
Every agent session generates traces and spans that flow into the telemetry pipeline. The built-in eval engine scores sessions so you can measure performance and iteratively improve your agents.

### Troubleshooting

**Server services fail to start**
Check that Docker and Docker Compose are running. Verify port availability (the stack uses multiple ports). Run `docker compose -f docker/docker-compose.yml ps` to check service status.

**CLI commands fail with authentication errors**
Run `observal auth login` to authenticate. On a fresh server this auto-creates an admin account. See [CLI Reference](docs/cli/README.md) for auth subcommands.

**No traces appearing in Grafana**
Ensure the OTEL collector is running and your IDE agents are instrumented with `observal doctor patch`. Check the collector logs with `docker compose -f docker/docker-compose.yml logs otel-collector`.

## Community

Have a question, idea, or want to share what you've built? Head to [GitHub Discussions](https://github.com/BlazeUp-AI/Observal/discussions). Please use Discussions for questions; open Issues for confirmed bugs and concrete feature requests.

Join the [Observal Discord](https://discord.observal.io) to chat directly with the maintainers and other community members.

## Security

To report a vulnerability, please use [GitHub Private Vulnerability Reporting](https://github.com/BlazeUp-AI/Observal/security/advisories) or email contact@blazeup.app. **Do not open a public issue.** See [SECURITY.md](SECURITY.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Star history

<a href="https://www.star-history.com/?repos=BlazeUp-AI%2FObserval&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=BlazeUp-AI/Observal&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=BlazeUp-AI/Observal&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=BlazeUp-AI/Observal&type=date&legend=top-left" />
 </picture>
</a>
