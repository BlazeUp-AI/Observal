# Kiro CLI Setup Guide for Observal

This guide walks you through connecting [Kiro CLI](https://kiro.dev) to Observal so you can:
- See Kiro sessions in the Observal dashboard with full tool-call telemetry
- Pull and install agents from the Observal registry into Kiro
- Run `observal doctor` to confirm everything is wired up correctly

> **No experience with Observal yet?** Start with [SETUP.md](../SETUP.md) for the full server setup, then return here. If you are running Kiro locally without a self-hosted Observal server, you can still use the CLI against a remote Observal instance — skip the Docker steps in SETUP.md and just install the CLI below.

---

## Quick Start

If you already have Observal running and authenticated, these five commands are all you need:

```bash
# 1. Install Kiro CLI
curl -fsSL https://cli.kiro.dev/install | bash

# 2. Log in to Kiro
kiro login

# 3. Wrap your existing Kiro MCP servers with the telemetry shim
observal scan --ide kiro

# 4. (Optional) Pull an agent from the Observal registry
observal pull <agent-id-or-name> --ide kiro

# 5. Confirm everything is configured correctly
observal doctor --ide kiro
```

---

## Prerequisites

Before starting, you need:

- **Observal CLI installed** — `pip install observal` or `uv tool install --editable .`
- **Authenticated with Observal** — run `observal auth login` (not the deprecated `observal login`)
- **Observal server reachable** — either self-hosted (see [SETUP.md](../SETUP.md)) or a remote instance

---

## Step 1 — Install Kiro CLI

### macOS / Linux

```bash
curl -fsSL https://cli.kiro.dev/install | bash
```

After installation, open a new terminal and verify it worked:

```bash
kiro --version
# Expected: kiro-cli 1.x.x (or similar)
```

### Windows

Download the installer from [kiro.dev/download](https://kiro.dev/download) and follow the setup wizard. Then verify in PowerShell:

```powershell
kiro --version
```

### Log in to Kiro

```bash
kiro login
```

This opens a browser for authentication. Once complete, Kiro is ready to use.

---

## Step 2 — Understand `observal-shim` (What it is and why it matters)

**`observal-shim`** is a small transparent proxy that sits between Kiro and each of your MCP servers. It never modifies tool calls — it only *observes* them. Every request and response becomes a telemetry span that streams into Observal for analysis.

```
Kiro  <-->  observal-shim  <-->  MCP Server
                  |
                  v (fire-and-forget)
           Observal API  -->  ClickHouse (traces, spans)
```

`observal-shim` is installed automatically as part of the Observal CLI. Verify it is available:

```bash
which observal-shim        # macOS/Linux
where observal-shim        # Windows
```

If the command is not found, reinstall the CLI: `uv tool install --editable .`

---

## Step 3 — Wrap Your Kiro MCP Servers

The `observal scan` command reads your Kiro config files, finds all registered MCP servers, and rewrites the config to route each server through `observal-shim`. A timestamped backup is created automatically before any changes are made.

```bash
# Wrap project-level MCP servers (.kiro/settings/mcp.json in the current directory)
observal scan --ide kiro

# Wrap global MCP servers (~/.kiro/settings/mcp.json)
observal scan --ide kiro --home

# Wrap both at once
observal scan --all-ides
```

**What to expect:** The command prints a summary table showing each MCP server found and whether it was successfully wrapped. Example output:

```
Scanning Kiro config...
  ✓ filesystem-server   wrapped  (was: npx @modelcontextprotocol/server-filesystem)
  ✓ github-mcp          wrapped  (was: npx @modelcontextprotocol/server-github)
  ✓ mcp-obsidian        wrapped  (was: npx mcp-obsidian)

Backup saved: .kiro/settings/mcp.json.20260414_182000.bak
3 server(s) instrumented.
```

If you see "0 server(s) instrumented", your Kiro config may be in a non-standard location. Check [Troubleshooting](#troubleshooting) below.

---

## Step 4 — Pull an Agent from the Observal Registry (Optional)

If you want to install a pre-built agent into Kiro:

```bash
# List available agents
observal agent list

# Install an agent by name or ID
observal pull <agent-id-or-name> --ide kiro
```

**What gets written to disk:**

| File | Purpose |
|------|---------|
| `~/.kiro/agents/<name>.json` | Agent config — includes the Observal telemetry hooks |
| `.kiro/steering/<name>.md` | Steering file — the agent's instructions loaded at session start |

**What a Kiro agent hook looks like** (inside `~/.kiro/agents/<name>.json`):

```json
{
  "name": "my-agent",
  "hooks": {
    "agentSpawn":       "curl -s -X POST http://localhost:8000/api/v1/otel/hooks ...",
    "userPromptSubmit": "curl -s -X POST http://localhost:8000/api/v1/otel/hooks ...",
    "preToolUse":       "curl -s -X POST http://localhost:8000/api/v1/otel/hooks ...",
    "postToolUse":      "curl -s -X POST http://localhost:8000/api/v1/otel/hooks ...",
    "stop":             "curl -s -X POST http://localhost:8000/api/v1/otel/hooks ..."
  }
}
```

These hooks fire automatically during Kiro sessions and send lifecycle events to Observal. You do not need to configure them manually — `observal pull` handles this.

---

## Step 5 — How Telemetry Reaches Observal

Kiro sends telemetry to Observal through two independent channels:

### Channel 1 — MCP tool calls (via `observal-shim`)

Every MCP tool call (set up in Step 3) is captured automatically and includes the tool name, input parameters, response, latency, and status.

### Channel 2 — Agent lifecycle events (via hooks)

Agents installed via `observal pull` include shell hooks that fire during Kiro sessions:

| Hook Event | What It Captures |
|------------|-----------------|
| `agentSpawn` | Session start |
| `userPromptSubmit` | The user's prompt text |
| `preToolUse` | Tool name and input (before the call) |
| `postToolUse` | Tool response (after the call) |
| `stop` | Session end, credit usage, model ID |

> **Note:** Kiro does not expose token counts — only billing credits. The Observal dashboard shows credits for Kiro sessions instead of token counts.

---

## Step 6 — Run Diagnostics

```bash
observal doctor --ide kiro
```

This checks the full integration end-to-end:

- ✓ Kiro CLI is installed and authenticated
- ✓ MCP servers are wrapped with `observal-shim`
- ✓ Agent files have Observal telemetry hooks
- ✓ Observal server is reachable at the configured URL

If any check fails, run with `--fix` to automatically apply suggested fixes:

```bash
observal doctor --ide kiro --fix
```

---

## Step 7 — View Your Traces

Open the Observal web UI at `http://localhost:3000/traces` (or your configured server URL) and filter by **IDE → Kiro** to see all Kiro sessions.

---

## Limitations

Kiro CLI has a few telemetry limitations compared to Claude Code that are outside Observal's control:

| Capability | Status |
|-----------|--------|
| Token counts (input/output) | ❌ Not available — Kiro exposes credits only |
| Cost per API call | ❌ Session-level credits only, not per-call |
| Model name | ⚠️ Often reported as `"auto"` — resolved from Kiro's local SQLite DB |
| Subagent tracking | ❌ Kiro has no subagent lifecycle events |
| Native OpenTelemetry | ❌ Not yet implemented upstream ([kirodotdev/Kiro#6319](https://github.com/kirodotdev/Kiro/issues/6319)) |

These limitations will resolve when Kiro implements native OTEL export.

---

## Troubleshooting

### `observal auth login` fails — "server not reachable"

The CLI cannot find your Observal server. Make sure the server is running and the URL is configured:

```bash
observal config show          # check what server URL is set
observal config set server_url http://localhost:8000
observal auth login
```

### `observal scan` wraps 0 servers

Your Kiro MCP config may be empty or in a different location. Check:

```bash
# Project-level MCP config
cat .kiro/settings/mcp.json

# Global MCP config
cat ~/.kiro/settings/mcp.json
```

If neither file exists, add at least one MCP server to Kiro first, then re-run `observal scan --ide kiro`.

### Hooks not firing — sessions not appearing in dashboard

1. Make sure `OBSERVAL_API_KEY` is set in your environment:
   ```bash
   echo $OBSERVAL_API_KEY    # macOS/Linux
   $env:OBSERVAL_API_KEY     # Windows PowerShell
   ```
2. Check that the agent JSON in `~/.kiro/agents/` has a `hooks` section (see example above).
3. Verify the server URL in the hook commands matches your Observal server (default: `http://localhost:8000`).

### `observal-shim` not found after scan

`observal-shim` must be on your PATH. Reinstall the CLI to ensure it is registered:

```bash
uv tool install --editable .
which observal-shim    # should print the path
```

### `observal doctor` reports issues but `--fix` doesn't resolve them

Run with verbose output and check the specific failure:

```bash
observal doctor --ide kiro --fix
observal auth status          # confirm server connectivity
```

If the server is unreachable, see [SETUP.md](../SETUP.md) for troubleshooting the Observal server itself.

---

## Related Docs

- [SETUP.md](../SETUP.md) — Full server setup and configuration
- [docs/cli.md](cli.md) — Complete CLI command reference
- [CONTRIBUTING.md](../CONTRIBUTING.md) — How to contribute to Observal
