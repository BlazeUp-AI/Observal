<!-- SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com> -->
<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# observal skill

Create, submit, manage, and install skills from the registry.

Skills are reusable capability packages that can be reviewed, published, and installed locally.

## Subcommands

| Command | Description |
| --- | --- |
| [`skill submit`](#observal-skill-submit) | Submit a new skill for review |
| [`skill list`](#observal-skill-list) | List approved skills |
| [`skill my`](#observal-skill-my) | List your own skills (all statuses) |
| [`skill show`](#observal-skill-show) | Show skill details |
| [`skill install`](#observal-skill-install) | Install a skill locally |
| [`skill edit`](#observal-skill-edit) | Edit a draft, rejected, or pending skill submission |
| [`skill delete`](#observal-skill-delete) | Delete a skill |

---

## `observal skill submit`

Submit a new skill to the registry for review.

```bash
observal skill submit
```

---

## `observal skill list`

List all approved skills available in the registry.

```bash
observal skill list
```

---

## `observal skill my`

List your own skills, including drafts, pending reviews, approved, and rejected submissions.

```bash
observal skill my
```

---

## `observal skill show`

Show detailed information about a skill.

```bash
observal skill show <id-or-name>
```

---

## `observal skill install`

Install a skill locally by fetching the full skill directory from git and writing it to disk.

```bash
observal skill install <id-or-name>
```

---

## `observal skill edit`

Edit a draft, rejected, or pending skill submission.

```bash
observal skill edit <id-or-name>
```

---

## `observal skill delete`

Delete a skill from the registry.

```bash
observal skill delete <id-or-name>
```

---

## Global options

### `--help`

Show help information for the command.

```bash
observal skill --help
```

---

## Related

* [`observal agent`](agent.md) — Bundle skills into installable agents.
* [`observal registry`](registry.md) — Manage registry components.