<!-- SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com> -->
<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# observal prompt

Manage prompt listings from the CLI. Prompts are reusable templates that can be submitted to the registry, rendered with variables, and installed into supported IDEs.

## Synopsis

```bash
observal prompt <command> [args] [options]
```

## Commands

| Command | What it does |
| --- | --- |
| `submit` | Submit a new prompt for review |
| `list` | List approved prompts |
| `my` | List your own prompts across all statuses |
| `show` | Show prompt details |
| `render` | Render a prompt template with variables |
| `install` | Generate install config for a prompt |
| `edit` | Edit a draft, rejected, or pending prompt submission |
| `delete` | Delete a prompt |

IDs can be UUIDs, names, row numbers from the last list output, or aliases created with [`observal config alias`](config.md).

## `observal prompt submit`

Submit a new prompt for review. Only submit prompts you created or are the point of contact for.

### Synopsis

```bash
observal prompt submit [OPTIONS]
```

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--from-file <text>` | `-f` | Create from JSON file or read template from file |
| `--draft` | | Save as draft instead of submitting for review |
| `--submit <prompt-id>` | | Submit an existing draft for review |

### Examples

```bash
observal prompt submit
observal prompt submit --from-file prompt.json --draft
observal prompt submit --submit 498c17ac-1234-4567-89ab-cdef01234567
```

## `observal prompt list`

List approved prompts.

### Synopsis

```bash
observal prompt list [OPTIONS]
```

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--category <text>` | `-c` | Filter by category |
| `--search <text>` | `-s` | Search prompts |
| `--output <text>` | `-o` | Output format: `table`, `json`, or `plain`; default `table` |

### Examples

```bash
observal prompt list
observal prompt list --search review
observal prompt list --category code-review --output json
```

## `observal prompt my`

List your own prompts across all statuses.

### Synopsis

```bash
observal prompt my [OPTIONS]
```

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--output <text>` | `-o` | Output format: `table`, `json`, or `plain`; default `table` |

## `observal prompt show`

Show details for one prompt.

### Synopsis

```bash
observal prompt show <prompt-id> [OPTIONS]
```

### Arguments

| Argument | Description |
| --- | --- |
| `<prompt-id>` | ID, name, row number, or `@alias` |

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--output <text>` | `-o` | Output format; default `table` |

## `observal prompt render`

Render a prompt template with variables.

### Synopsis

```bash
observal prompt render <prompt-id> [--var key=value ...]
```

### Arguments

| Argument | Description |
| --- | --- |
| `<prompt-id>` | Prompt ID, name, row number, or `@alias` |

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--var <key=value>` | `-v` | Variable to inject; repeat for multiple variables |

### Example

```bash
observal prompt render code-review --var language=python --var focus=security
```

## `observal prompt install`

Generate install config for a prompt.

### Synopsis

```bash
observal prompt install <prompt-id> --ide <ide> [--raw]
```

### Arguments

| Argument | Description |
| --- | --- |
| `<prompt-id>` | Prompt ID, name, row number, or `@alias` |

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--ide <text>` | `-i` | Target IDE; required |
| `--raw` | | Output raw JSON only |

## `observal prompt edit`

Edit a draft, rejected, or pending prompt submission.

### Synopsis

```bash
observal prompt edit <prompt-id> [OPTIONS]
```

### Arguments

| Argument | Description |
| --- | --- |
| `<prompt-id>` | ID, name, row number, or `@alias` |

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--from-file <text>` | `-f` | Load updates from a JSON file |
| `--name <text>` | `-n` | New listing name |
| `--description <text>` | `-d` | New description |
| `--version <text>` | `-v` | New version string |
| `--category <text>` | `-c` | New category |
| `--template <text>` | `-t` | New template text |

## `observal prompt delete`

Delete a prompt.

### Synopsis

```bash
observal prompt delete <prompt-id> [OPTIONS]
```

### Arguments

| Argument | Description |
| --- | --- |
| `<prompt-id>` | ID, name, row number, or `@alias` |

### Options

| Option | Short | Description |
| --- | --- | --- |
| `--yes` | `-y` | Skip confirmation |

## Related

* [`observal agent`](agent.md)
* [`observal registry`](registry.md)
* [`observal config`](config.md)
