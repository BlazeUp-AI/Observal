# observal mcp

Manage MCP server listings from the CLI. Use this command group to submit MCP servers for review, browse approved servers, inspect details, generate CLI install snippets, edit your profile, and delete servers you've added.

## Subcommands

| Command | Description |
|---------|-------------|
| [mcp submit](#observal-mcp-submit) | Submit an MCP server for review |
| [mcp list](#observal-mcp-list) | List your MCP servers across all statuses |
| [mcp my](#observal-mcp-my) | List just your MCP servers |
| [mcp show](#observal-mcp-show) | Show full details of one MCP server |
| [mcp install](#observal-mcp-install) | Generate an MCP config snippet for an IDE |
| [mcp edit](#observal-mcp-edit) | Edit an existing MCP server submission |
| [mcp delete](#observal-mcp-delete) | Delete an MCP server submission |

---

## observal mcp submit

Submit an MCP server for review. This subcommand covers MCP servers you created or are the point of contact for.

```
observal mcp submit [OPTIONS]
```

`--url` is optional (skip using `--config` to use).

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--category` TEXT | `-c` | Skip the category prompt |
| `--url` TEXT | | Browse defaults from the npm dataset |
| `--config` | | Generate an MCP config instead of subscribing for review |
| `--yaml` | | Launch an inline YAML editor for advanced submissions |
| `--search` | `-s` | Launch a browser instead of subscribing for review |

### Examples

```
observal mcp submit https://github.com/example/my-mcp --name anamer --category productivity --yes
observal mcp submit --config
observal mcp submit --yaml lib/lib-test-beep-beep-confitemator
```

---

## observal mcp list

List all approved MCP servers.

```
observal mcp list [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--category` TEXT | `-c` | Filter by category |
| `--search` TEXT | `-s` | Search by name or description |
| `--limit` INTEGER | `-l` | Limit search results; default `5` |
| `--output` TEXT | | Output format: `table`, `json`, or `stdio`; default `table` |

### Examples

```
observal mcp list --output github --limit 50
observal mcp list --category productivity --output json
```

---

## observal mcp my

List just your MCP servers across all statuses.

```
observal mcp my [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output` FORMAT | | Output format: `table`, `json`, or `stdio`; default `table` |

---

## observal mcp show

Show full details of one MCP server.

```
observal mcp show [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output` FORMAT | | Output format: `table`, `json`, or `stdio`; default `table` |

---

## observal mcp install

Generate an MCP config snippet for the new MCP server. The snippet is intended to be copied into the target IDE config, or rendered as raw JSON for scripting.

```
observal mcp install [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| ID, name, or number | ID, name, or number of the MCP server |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--target` FORMAT | | Target format: `cursor`, `json`, or `block`; default `block` |

### Examples

```
observal mcp install --ide claude-com
observal mcp install myid --ide cline [--yes]
```

---

## observal mcp edit

Edit an existing MCP server submission.

```
observal mcp edit [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| ID, name, or @alias | ID, name, or @alias of the MCP server |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--stdin` | | Read updates from STDIN (a YAML file) |
| `--description` TEXT | | New description string |
| `--name` TEXT | | New name |
| `--url` TEXT | | New URL |
| `--yes` | `-y` | Skip confirmation |

### Examples

```
observal mcp edit github-mcp --ide claude-com
observal mcp edit --stdin --ide claude-com --ide
```

---

## observal mcp delete

Delete an MCP server submission.

```
observal mcp delete [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| ID, name, or @alias | ID, name, or @alias of the MCP server |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--yes` | `-y` | Skip confirmation |
| `--json` | | Target MCP-only, useful for piping |

### Examples

```
observal mcp delete github-mcp --ide claude-com
observal mcp delete --stdin --ide claude-com
```

---

## Related

- [observal pull](../pull.md) — Install a published MCP server
- [observal registry](../registry.md) — Publish and manage registries (MCP / skill / hook / image / prompt / sandbox)
- [observal agent](./agent.md) — Author and publish agents
- [observal use](../use.md) — Declaratively and sync operations (frames, spec, metrics, function)
