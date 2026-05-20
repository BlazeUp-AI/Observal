# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Push JSONL session transcript data to the Observal server.

Invoked by Claude Code hooks as:
    python -m observal_cli.hooks.session_push

Receives hook event data via stdin (JSON).  Reads new lines from the
session JSONL file since last push and POSTs them to the ingest endpoint.
"""

import json
import sys
from pathlib import Path

from observal_cli.sessions.base import (
    build_payload,
    load_config,
    log_error,
    post_to_server,
    read_cursor,
    read_new_lines,
    write_cursor,
)
from observal_cli.sessions.claude_code import (
    find_jsonl_file,
    get_parent_session_id,
    project_key_from_cwd,
    push_subagent_sessions,
)


def main(home: Path | None = None) -> None:
    """Main entry point.  Never raises -- hooks must not break the IDE."""
    try:
        _run(home=home)
    except Exception:
        pass


def _run(home: Path | None = None) -> None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except Exception:
        return

    hook_event = event.get("hook_event_name", "")
    session_id = event.get("session_id", "")
    cwd = event.get("cwd", "")

    if not session_id:
        return

    config = load_config(home=home)
    if config is None:
        return

    project_key = project_key_from_cwd(cwd)
    jsonl_path = find_jsonl_file(session_id, project_key, home=home)
    if jsonl_path is None:
        return

    parent_session_id = get_parent_session_id(jsonl_path)

    offset, line_count = read_cursor(session_id, home=home)
    lines, bytes_read = read_new_lines(jsonl_path, offset=offset)

    if not lines:
        return

    new_offset = offset + bytes_read
    payload = build_payload(
        session_id=session_id,
        lines=lines,
        start_offset=line_count,
        hook_event=hook_event,
        line_count_before=line_count,
        new_offset=new_offset,
        cwd=cwd,
        parent_session_id=parent_session_id,
        session_jsonl=jsonl_path,
    )

    success = post_to_server(
        server_url=config["server_url"],
        access_token=config["access_token"],
        payload=payload,
        config=config,
    )

    if not success:
        log_error(
            f"session_push: POST failed for session {session_id} (offset {offset}-{new_offset})",
            home=home,
        )
        return

    write_cursor(session_id, new_offset, line_count + len(lines), finalized=False, home=home)

    if parent_session_id is None:
        push_subagent_sessions(session_id, jsonl_path, config, cwd=cwd, home=home)

    if hook_event == "Stop":
        _spawn_tail_flush(session_id)
    else:
        _spawn_crash_recovery()


def _spawn_crash_recovery() -> None:
    import subprocess

    try:
        subprocess.Popen(
            [sys.executable, "-m", "observal_cli.cmd_reconcile"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def _spawn_tail_flush(session_id: str) -> None:
    import subprocess

    try:
        subprocess.Popen(
            [sys.executable, "-m", "observal_cli.cmd_tail_flush", session_id],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
