# Observal

MCP server registry platform: CLI (`observal_cli/`), FastAPI server (`observal-server/`), Next.js web (`web/`).

## Architecture (server)

- FastAPI + SQLAlchemy async (PostgreSQL). Session factory: `database.async_session`.
- Auth: JWT or API key via `api/deps.py:get_current_user`.
- Registry types: MCP, Hook, Prompt, Sandbox, Skill — each has models, schemas, routes, and services.
- MCP validation pipeline (`services/mcp_validator.py`):
  - `analyze_repo(git_url)` — clones repo (shallow, depth=1) via GitPython `Repo.clone_from` in a thread, scans for MCP patterns (Python regex, TS package.json, Go imports), AST-parses Python entry points, detects required env vars (`os.environ`/`os.getenv`, `.env.example`, Dockerfile `ENV`/`ARG`).
  - `run_validation(listing, db)` — Stage 1: clone & inspect, Stage 2: manifest validation (AST checks for tools, docstrings, type annotations). Runs as a **background task** after submit (not inline).
  - Environment variables: stored in `McpListing.environment_variables` (JSON). Detected during analysis, confirmed by publisher at submit, prompted to installer at install time. Config generator merges them into IDE config `env` blocks.
  - Auth for private repos: `GIT_CLONE_TOKEN` + `GIT_CLONE_TOKEN_USER` env vars (supports GitHub `x-access-token` and GitLab `oauth2`/`private-token`).
  - Internal URLs: blocked by default, `ALLOW_INTERNAL_URLS=true` for self-hosted.
  - Clone timeout: `GIT_CLONE_TIMEOUT` env var (default 120s).

## CLI (`observal_cli/`)

- Typer-based. Canonical commands under `observal registry {type} {action}`. Deprecated root aliases exist.
- `cmd_mcp.py:_submit_impl` calls `/analyze` first (prefill), then `/submit`. Interactive prompts use `questionary` via `prompts.py`.

## Lint / Format

- `ruff` (config in `pyproject.toml`). Line length 120, Python 3.11+.
- Run: `uvx ruff check` / `uvx ruff format`.

## Tests

- `pytest` + `pytest-asyncio`. Test files in `tests/`.
