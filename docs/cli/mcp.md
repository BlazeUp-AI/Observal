<!-- SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com> -->
<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# observal mcp

Manage MCP server listings from the CLI. Use this command group to submit MCP servers for review, browse approved servers, inspect details, generate IDE install snippets, edit your drafts, and delete servers you own.

## Synopsis

```bash
observal mcp <command> [args] [options]
```

## Commands

| Command | What it does |
| --- | --- |
| `submit` | Submit an MCP server for review |
| `list` | List approved MCP servers |
| `my` | List your own MCP servers across all statuses |
| `show` | Show full details for one MCP server |
| `install` | Generate an IDE config snippet for one MCP server |
| `edit` | Edit a draft, rejected, or pending MCP server submission |
| `delete` | Delete an MCP server |

IDs can be UUIDs, names, row numbers from the last list output, or aliases created with [`observal config alias`](config.md).

## `observal mcp submit`

Submit an MCP server for review. Only submit servers you created or are the point of contact for.

### Synopsis

```bash
observal mcp submit [GIT_URL] [OPTIONS]
```

`GIT_URL` is optional only when `--config` is used.

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--name <text>` | `-n` | Skip the name prompt |
| `--category <text>` | `-c` | Skip the category prompt |
| `--yes` | `-y` | Accept defaults from repo analysis |
| `--config` | | Submit via direct JSON config paste mode |
| `--draft` | | Save as draft instead of submitting for review |
| `--submit <mcp-id>` | | Submit an existing draft for review |

### Examples

```bash
observal mcp submit https://github.com/example/weather-mcp
observal mcp submit https://github.com/example/weather-mcp --name weather --category productivity --yes
observal mcp submit --config --draft
observal mcp submit --submit 498c17ac-1234-4567-89ab-cdef01234567
```

## `observal mcp list`

List approved MCP servers.

### Synopsis

```bash
observal mcp list [OPTIONS]
```

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--category <text>` | `-c` | Filter by category |
| `--search <text>` | `-s` | Search by name or description |
| `--interactive` | `-i` | Use interactive search mode |
| `--limit <integer>` | `-n` | Maximum results, default `50` |
| `--sort <text>` | | Sort by `name`, `category`, or `version`; default `name` |
| `--output <text>` | `-o` | Output format: `table`, `json`, or `plain`; default `table` |

### Examples

```bash
observal mcp list
observal mcp list --search github --limit 20
observal mcp list --category productivity --output json
```

## `observal mcp my`

List your own MCP servers across all statuses.

### Synopsis

```bash
observal mcp my [OPTIONS]
```

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--output <text>` | `-o` | Output format: `table`, `json`, or `plain`; default `table` |

## `observal mcp show`

Show full details of one MCP server.

### Synopsis

```bash
observal mcp show <mcp-id> [OPTIONS]
```

### Arguments

| Argument | Description |
| --- | --- |
| `<mcp-id>` | ID, name, row number, or `@alias` |

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--output <text>` | `-o` | Output format: `table` or `json`; default `table` |

## `observal mcp install`

Generate an IDE config snippet for one MCP server. The output is intended to be copied into the target IDE config, or emitted as raw JSON for scripting.

### Synopsis

```bash
observal mcp install <mcp-id> --ide <ide> [--raw]
```

### Arguments

| Argument | Description |
| --- | --- |
| `<mcp-id>` | ID, name, row number, or `@alias` |

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--ide <text>` | `-i` | Target IDE; required |
| `--raw` | | Output raw JSON only, useful for piping |

### Examples

```bash
observal mcp install github --ide claude-code
observal mcp install @github-mcp --ide cursor --raw
```

## `observal mcp edit`

Edit a draft, rejected, or pending MCP server submission.

### Synopsis

```bash
observal mcp edit <mcp-id> [OPTIONS]
```

### Arguments

| Argument | Description |
| --- | --- |
| `<mcp-id>` | ID, name, row number, or `@alias` |

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--from-file <text>` | `-f` | Load updates from a JSON file |
| `--name <text>` | `-n` | New listing name |
| `--description <text>` | `-d` | New description |
| `--category <text>` | `-c` | New category |
| `--version <text>` | `-v` | New version string |
| `--git-url <text>` | | New Git URL |
| `--command <text>` | | New command |
| `--url <text>` | | New URL |

### Examples

```bash
observal mcp edit @github-mcp --description "GitHub MCP server for repository automation"
observal mcp edit 498c17ac-1234-4567-89ab-cdef01234567 --from-file update.json
```

## `observal mcp delete`

Delete an MCP server.

### Synopsis

```bash
observal mcp delete <mcp-id> [OPTIONS]
```

### Arguments

| Argument | Description |
| --- | --- |
| `<mcp-id>` | ID, name, row number, or `@alias` |

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--yes` | `-y` | Skip confirmation |

## Related

* [`observal registry`](registry.md)
* [`observal agent`](agent.md)
* [`observal config`](config.md)
