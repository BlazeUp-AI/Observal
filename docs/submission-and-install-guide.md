# Observal: Submission & Install Guide

All registry types follow the same CLI pattern: submit, list, show, install, delete. All commands accept either a UUID or a name.

Submitters can install and use their own items immediately — admin approval only controls visibility in the public registry.

---

## Quick Start: Auto-Detect Existing Setup

Already have MCP servers configured in your IDE? Skip manual registration:

```bash
observal scan              # auto-detect IDE, register & instrument everything
observal scan --dry-run    # preview what would change
observal scan --ide cursor # target a specific IDE
observal scan /path/to/project --yes  # non-interactive
```

This detects MCP servers from your IDE config files, registers them with Observal, and wraps them with `observal-shim` for telemetry collection. A backup of your original config is created automatically.

---

## Submitting Items

### MCP Servers

```bash
observal submit https://github.com/your-org/your-mcp-server.git
```

Your repo needs a FastMCP (Python) server with:
- A server name and description
- Every tool has a description (docstring or `description` param)
- Every tool has typed input parameters (no bare `**kwargs`)

### Agents

```bash
observal agent create              # interactive
observal agent create --from-file agent.yaml  # from file
```

An agent is a configuration object: system prompt + MCP servers + model config + goal template.

### Tools, Skills, Hooks, Prompts, Sandboxes, GraphRAGs

```bash
observal tool submit
observal skill submit <git-url-or-path>
observal hook submit
observal prompt submit [--from-file <path>]
observal sandbox submit
observal graphrag submit
```

All submit commands walk you through the required fields interactively.

---

## Installing Items

Install generates an IDE-specific config snippet and wraps the command with the appropriate telemetry proxy:

| Transport | Proxy | Used By |
|-----------|-------|---------|
| stdio | `observal-shim` | MCP servers (default) |
| HTTP | `observal-proxy` | HTTP tools |
| Docker | `observal-sandbox-run` | Sandboxes |
| HTTP | `observal-graphrag-proxy` | GraphRAG endpoints |

### Commands

```bash
observal install <id-or-name> --ide <ide>        # MCP servers
observal agent install <id-or-name> --ide <ide>   # Agents (generates rules file + MCP config)
observal tool install <id-or-name> --ide <ide>
observal skill install <id-or-name> --ide <ide>
observal hook install <id-or-name> --ide <ide>
observal prompt install <id-or-name> --ide <ide>
observal sandbox install <id-or-name> --ide <ide>
observal graphrag install <id-or-name> --ide <ide>
```

Use `--raw` to pipe config directly to a file.

### IDE Config Paths

| IDE | MCP Config | Rules / System Prompt |
|-----|------------|-----------------------|
| Kiro IDE / Kiro CLI | `.kiro/mcp.json` | `.kiro/rules/` |
| Cursor | `.cursor/mcp.json` | `.rules/` |
| Claude Code | `claude mcp add ...` | `.claude/rules/` |
| VS Code | `.vscode/mcp.json` | — |
| Windsurf | `.windsurf/mcp.json` | — |
| Gemini CLI | `.gemini/settings.json` | `GEMINI.md` |
| Codex CLI | `.codex/mcp.json` | — |

### IDE Support Matrix

| IDE | MCP | Agents | Skills | Hooks | Sandbox | GraphRAGs | Prompts | Native OTel |
|-----|:---:|:------:|:------:|:-----:|:-------:|:---------:|:-------:|:-----------:|
| Claude Code | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Codex CLI | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| Gemini CLI | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| GitHub Copilot | — | — | ✓ | — | — | — | ✓ | ✓ |
| Kiro IDE | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Kiro CLI | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Cursor | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| VS Code | ✓ | ✓ | — | — | ✓ | ✓ | ✓ | — |
| Windsurf | ✓ | ✓ | — | — | ✓ | ✓ | ✓ | — |

---

## Admin Review

All registry types go through a single review workflow:

```bash
observal review list [--type mcp|agent|skill|hook|tool|prompt|sandbox|graphrag]
observal review show <id>
observal review approve <id>
observal review reject <id> --reason "Missing documentation"
```

---

## Quick Reference

| Action | CLI Command |
|--------|-------------|
| Auto-detect & instrument | `observal scan` |
| Submit MCP | `observal submit <git-url>` |
| Submit agent | `observal agent create` |
| Submit tool | `observal tool submit` |
| Submit skill | `observal skill submit <git-url-or-path>` |
| Submit hook | `observal hook submit` |
| Submit prompt | `observal prompt submit` |
| Submit sandbox | `observal sandbox submit` |
| Submit GraphRAG | `observal graphrag submit` |
| Install any type | `observal <type> install <id-or-name> --ide <ide>` |
| List any type | `observal <type> list` |
| Show any type | `observal <type> show <id-or-name>` |
| Delete any type | `observal <type> delete <id-or-name>` |
| Review pending | `observal review list` |
| Approve | `observal review approve <id>` |
| Reject | `observal review reject <id> --reason "..."` |
