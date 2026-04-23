# Gemini CLI

Gemini CLI is supported at the MCP, rules, hook bridge, and OTLP telemetry level.

## What you get

* **MCP server instrumentation** — `observal scan --ide gemini-cli`
* **Rules files** — `AGENTS.md` or `GEMINI.md`
* **OTLP telemetry** — `observal scan` configures `~/.gemini/settings.json` to export traces via OTLP
* **Hook bridge** — `observal scan` injects hooks into `~/.gemini/settings.json` to capture prompts, tool I/O, agent responses, and session lifecycle events

## Setup

```bash
curl -fsSL https://raw.githubusercontent.com/BlazeUp-AI/Observal/main/install.sh | bash
observal auth login

observal scan --ide gemini-cli
observal doctor --ide gemini-cli
```

Restart Gemini CLI.

## Config file

`.gemini/settings.json` in your project directory.

## Install an agent

```bash
observal pull <agent-id> --ide gemini-cli
```

Writes MCP config + rules files. OTLP telemetry and hooks are configured automatically by `observal scan`.

## Known issues

* Support is labeled "limited" because we have less test coverage here than for Claude Code / Kiro. Feedback welcome on [GitHub Discussions](https://github.com/BlazeUp-AI/Observal/discussions).

## Related

* [`observal scan`](../cli/scan.md)
* [Use Cases → Observe MCP traffic](../use-cases/observe-mcp-traffic.md)
