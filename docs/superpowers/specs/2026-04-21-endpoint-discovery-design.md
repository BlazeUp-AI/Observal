# Endpoint Discovery

Replace all hardcoded and derived OTLP/hooks URLs with a server-side discovery endpoint. The server is the single source of truth for its own topology. Clients fetch endpoint URLs at login and save them to config.

## Problem

Hook scripts, config generators, and IDE setup code hardcode `localhost:8000` (API), `localhost:4317` (OTLP gRPC), and `localhost:4318` (OTLP HTTP) or derive them by swapping ports on the server URL. This breaks in production/enterprise deployments where:

- Ports are remapped by the admin
- A reverse proxy fronts the stack
- The OTLP collector runs on non-default ports

There is no single source of truth — every consumer guesses independently.

## Design

### Server Config

Three new settings in `observal-server/config.py` `Settings`:

```python
PUBLIC_URL: str = ""        # e.g. "https://observal.company.com"
OTLP_HTTP_URL: str = ""     # e.g. "https://observal.company.com:4318"
OTLP_GRPC_URL: str = ""     # e.g. "https://observal.company.com:4317"
```

Derivation when empty:

- `PUBLIC_URL` empty: derived from `Request.base_url` at runtime.
- `OTLP_HTTP_URL` empty: derived from `PUBLIC_URL` — same hostname, port 4318, http for localhost else https.
- `OTLP_GRPC_URL` empty: same pattern, port 4317.

Zero config for local dev. One env var (`PUBLIC_URL`) for production. Admin only sets OTLP URLs explicitly if ports are remapped.

### Discovery Endpoint

`GET /api/v1/config/endpoints` — no auth required.

```json
{
  "api": "https://observal.company.com",
  "otlp_http": "https://observal.company.com:4318",
  "otlp_grpc": "https://observal.company.com:4317",
  "web": "https://observal.company.com:3000"
}
```

`web` comes from the existing `FRONTEND_URL` setting.

### Auth Login Flow

Current: prompt server URL → `/health` → login → derive OTLP ports client-side → configure IDEs.

New: prompt server URL → `/health` → login → **`GET /api/v1/config/endpoints`** → save all URLs to config → configure IDEs using discovered URLs.

### Client Config

`~/.observal/config.json` gains three fields:

```json
{
  "server_url": "https://observal.company.com",
  "otlp_http_url": "https://observal.company.com:4318",
  "otlp_grpc_url": "https://observal.company.com:4317",
  "web_url": "https://observal.company.com:3000",
  "access_token": "...",
  "refresh_token": "...",
  "user_id": "...",
  "user_name": "..."
}
```

### Consumer Changes

No code derives or hardcodes URLs anymore. Every consumer reads from config or settings.

**CLI-side (read from `~/.observal/config.json`):**

| File | What changes |
|------|-------------|
| `hooks_spec.py` `get_desired_env()` | Reads `otlp_grpc_url` from config instead of deriving `{hostname}:4317` |
| `cmd_auth.py` IDE setup (Gemini, Codex, Claude Code) | Reads `otlp_http_url` / `otlp_grpc_url` from config |
| `kiro_hook.py`, `kiro_stop_hook.py` | Reads `server_url` from config for hooks URL |
| `flush_buffer.py` | Reads `server_url` from config for hooks URL |
| `observal-hook.sh`, `observal-stop-hook.sh` | Reads `server_url` from config for hooks URL |
| `cmd_doctor.py` | Reads actual URLs from config for diagnostics |
| `cmd_ops.py` | Already reads from config — no change needed |
| `cmd_scan.py` | Already reads from config — no change needed |

**Server-side (read from `Settings` or `Request`):**

| File | What changes |
|------|-------------|
| `config_generator.py` | Receives `otlp_http_url` from route; remove `derive_otlp_url` |
| `agent_config_generator.py` | Receives `server_url` (hooks) and `otlp_http_url` (OTLP) as separate params |
| `agent_builder.py` | `generate_ide_agent_files()` takes `server_url` param; reads OTLP from settings |
| `hook_config_generator.py` | Receives `server_url` from route |
| `skill_config_generator.py` | Receives `server_url` from route |
| `sandbox_config_generator.py` | Receives `server_url` from route |
| Install routes (mcp, hook, skill, sandbox, agent) | Derive URLs from settings + request, pass to generators |

### Error Handling

If CLI commands need a URL and the user hasn't logged in (no config file), error with: "Run `observal auth login` first." No silent fallback to localhost.

### What Gets Deleted

- All `derive_otlp_url()` functions and callers
- All `localhost:8000` / `localhost:4317` / `localhost:4318` hardcoded fallbacks in hook scripts and generators
- All port-derivation logic (`urlparse` + port swap patterns) in `hooks_spec.py`, `cmd_auth.py`, `config_generator.py`
- The `_resolve_hooks_url()` functions added in the current PR (superseded by config reads)

### Testing

- Unit tests for the discovery endpoint (returns correct URLs from settings, derives when empty)
- Unit tests for auth login flow (discovery response saved to config)
- Update existing generator tests to pass URLs explicitly instead of relying on defaults
- Integration: `observal auth login` → verify config file has all four URLs → verify IDE configs use them
