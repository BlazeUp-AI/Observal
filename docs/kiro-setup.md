# Kiro CLI Setup Guide for Observal

This guide explains how to connect Kiro CLI to Observal for telemetry collection, agent management, and observability.

## Prerequisites

- Observal server running (`make up` or `docker compose up -d`)
- `observal` CLI installed (`uv tool install --editable .`)
- Authenticated with Observal (`observal login`)

## 1. Install Kiro CLI

```bash
curl -fsSL https://cli.kiro.dev/install | bash
kiro-cli --version
kiro-cli login
```

## 2. Configure MCP Telemetry (via observal-shim)

Observal wraps MCP servers with `observal-shim` to capture tool call telemetry. Scan your Kiro config to auto-wrap:

```bash
# Wrap project-level MCP servers
observal scan --ide kiro

# Wrap global MCP servers
observal scan --ide kiro --home
```

This modifies `.kiro/settings/mcp.json` to route MCP calls through observal-shim.

## 3. Install an Agent from Observal Registry

```bash
# List available agents
observal agent list

# Pull agent config for Kiro
observal pull <agent-id-or-name> --ide kiro

# This writes:
#   ~/.kiro/agents/<name>.json    — Agent config with hooks
#   .kiro/steering/<name>.md      — Steering file (instructions)
```

## 4. How Telemetry Works

Kiro does **not** have native OpenTelemetry export (as of v1.28). Observal collects telemetry through two channels:

### Channel 1: observal-shim (MCP tool calls)
Every MCP server wrapped with observal-shim reports tool calls, latency, and status to Observal.

### Channel 2: Hook bridge (agent lifecycle)
Agents pulled from Observal include shell hooks that POST lifecycle events to the Observal API:

| Kiro Hook Event | What It Captures |
|-----------------|-----------------|
| `agentSpawn` | Session start |
| `preToolUse` | Tool invocation (before) |
| `postToolUse` | Tool result (after) |
| `stop` | Session end |
| `userPromptSubmit` | User prompt text |

These hooks call `curl` to send JSON payloads to `http://localhost:8000/api/v1/telemetry/hooks`.

## 5. Verify Setup

```bash
observal doctor --ide kiro
```

This checks:
- Kiro CLI is installed and authenticated
- MCP servers are wrapped with observal-shim
- Agents have Observal telemetry hooks
- Observal server is reachable

## 6. View Traces

Open the Observal web UI at `http://localhost:3000/traces` and filter by IDE → "kiro" to see Kiro traces.

## Limitations

- **No token counts**: Kiro doesn't expose input/output token counts in hooks
- **No model name**: The model used per request isn't available in hook payloads
- **No cost data**: Credit consumption isn't exportable
- **No native OTEL**: Waiting on upstream Kiro support ([kirodotdev/Kiro#6319](https://github.com/kirodotdev/Kiro/issues/6319))

These limitations will resolve when Kiro implements native OTEL export.

## Troubleshooting

### Hooks not firing
- Ensure `OBSERVAL_API_KEY` is set in your environment
- Check that the agent JSON in `~/.kiro/agents/` has a `hooks` section
- Verify the server URL is correct (default: `http://localhost:8000`)

### MCP servers not reporting telemetry
- Run `observal scan --ide kiro` to re-wrap servers
- Check that `observal-shim` is in your PATH: `which observal-shim`

### Doctor reports issues
- Run `observal doctor --ide kiro --fix` for suggested fixes
