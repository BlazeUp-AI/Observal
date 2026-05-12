<!-- SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com> -->
<!-- SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com> -->
<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# reconcile recovery helper

`observal_cli.cmd_reconcile` is the crash-recovery scanner for session JSONL ingestion. It is not a public `observal` subcommand; it runs as a small Python module so hooks can launch it in the background without blocking your IDE.

## What it does

When an IDE exits cleanly, the Stop hook pushes the final tail of the session JSONL file and marks the cursor as finalized. If the IDE is killed, crashes, or exits before Stop fires, the local cursor can have unsynced bytes.

The reconcile helper:

1. Reads `~/.observal/sync_state.json`.
2. Finds sessions that are not finalized.
3. Looks up the matching JSONL file under Claude Code or Kiro session directories.
4. Skips sessions that are still active, too old, or have no new bytes.
5. Pushes the remaining JSONL tail as a synthetic Stop event.
6. Marks the cursor finalized after a successful push.

This prevents lost final turns after a hard kill or missed Stop hook.

## When it runs automatically

Claude Code and Kiro hooks spawn the reconciler after non-Stop events:

```bash
python -m observal_cli.cmd_reconcile
```

The spawn is best-effort and detached. Hook execution continues even if the background process cannot start.

The helper only recovers sessions whose JSONL file is idle for at least two minutes and no older than seven days. That delay avoids pushing the tail of a session that is still being written.

## Run it manually

Use manual invocation when a session is missing final turns in Observal after an IDE crash:

```bash
python -m observal_cli.cmd_reconcile
```

It uses the same local auth/config file as hooks:

```text
~/.observal/config.json
```

If the config file is missing, the server URL is missing, or no access token/API key is available, the helper exits without changing anything.

## Output and logs

The reconciler is quiet by design. A successful run normally prints nothing.

Useful files:

| Path | Purpose |
| --- | --- |
| `~/.observal/sync_state.json` | Per-session cursor offsets, line counts, and `finalized` status |
| `~/.observal/sync.log` | Hook ingestion errors written by the session push pipeline |

If a recovered tail still does not appear in Observal, check:

```bash
cat ~/.observal/sync.log
cat ~/.observal/sync_state.json
```

Common causes are an expired token, an unreachable Observal server, or a session file that is still newer than the two-minute stale threshold.

## Session files scanned

The helper searches recent session files in:

| IDE | Path |
| --- | --- |
| Claude Code | `~/.claude/projects/<project>/<session_id>.jsonl` |
| Claude Code subagents | `~/.claude/projects/<project>/<session_id>/subagents/<agent_id>.jsonl` |
| Kiro | `~/.kiro/sessions/cli/<session_id>.jsonl` |

Only sessions modified within the last seven days are considered.

## Related

* [`observal doctor`](doctor.md)
* [`observal scan`](scan.md)
* [Telemetry pipeline](../self-hosting/telemetry-pipeline.md)
