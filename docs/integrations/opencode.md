<!-- SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com> -->
<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# OpenCode

OpenCode is supported at the MCP, rules, and hook bridge level. It uses `~/.config/opencode/opencode.json` for user-level MCP configuration and `AGENTS.md` for project rules.

## What you get

* **MCP server instrumentation** -- `observal doctor patch --shim --ide opencode` wraps MCP servers via `observal-shim`
* **Rules files** -- OpenCode reads `AGENTS.md` in a project or `~/.config/opencode/AGENTS.md` for user-level rules
* **Hook bridge** -- `observal pull` writes an OpenCode plugin that forwards telemetry hook events to Observal

## What you don't get

* No native OTLP telemetry
* No steering files
* Hook coverage depends on the lifecycle events exposed by OpenCode's plugin API

If native OTLP matters, use Claude Code, Kiro, or Gemini CLI instead.

## Setup

```bash
curl -fsSL https://raw.githubusercontent.com/BlazeUp-AI/Observal/main/install.sh | bash
observal auth login

observal scan --ide opencode                         # see what's there
observal doctor patch --all --ide opencode            # instrument it
observal doctor --ide opencode                        # verify
```

Restart OpenCode after patching so it reloads the config and plugin files.

## Config file

`~/.config/opencode/opencode.json` stores user-level MCP servers under the `mcp` key. After `doctor patch --shim`, local MCP entries route through `observal-shim`. A timestamped `.bak` is saved next to the file before it is modified.

Project-level rules live in `AGENTS.md`. User-level rules live in `~/.config/opencode/AGENTS.md`.

## Install an agent

```bash
observal pull <agent-id> --ide opencode
```

What gets written:

* MCP servers appended to `~/.config/opencode/opencode.json`
* `AGENTS.md` for project scope, or `~/.config/opencode/AGENTS.md` for user scope
* `.opencode/plugins/observal-plugin.mjs` for hook telemetry

Use OpenCode's user scope when you want the agent available across projects; use project scope when the rules should stay with one repository.

## Caveats

* OpenCode's MCP config is user-level by default. Run `observal scan --ide opencode` before patching if you maintain multiple OpenCode profiles.
* Restart OpenCode after `observal pull` or `doctor patch` to avoid stale MCP/plugin state.
* Without native OTLP, telemetry comes from MCP shims and the OpenCode plugin bridge.

## Related

* [`observal scan`](../cli/scan.md)
* [Use Cases -> Observe MCP traffic](../use-cases/observe-mcp-traffic.md)
