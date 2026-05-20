# SPDX-FileCopyrightText: 2026 Lokesh Selvam <lokeshselvam7025@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Push Cursor session transcript data to the Observal server.

Mirrors observal_cli.hooks.session_push but for Cursor's hook events:

  Hook events:    beforeSubmitPrompt, stop
  Transcript:     path provided via transcript_path field in hook payload
  Cursor state:   ~/.observal/sync_state.json  (shared with Claude Code)

Invoked by Cursor hooks as:
    python -m observal_cli.hooks.cursor_session_push

Receives hook event data via stdin (JSON).  Reads new lines from the
transcript file since last push and POSTs them to the ingest endpoint.

Cursor provides transcript_path directly in the hook payload, so we don't
need to compute it.  The server-side parser reuses the claude-code
classifier since the transcript format is compatible.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from observal_cli.hooks.session_push import (
    build_payload,
    load_config,
    post_to_server,
    read_cursor,
    read_new_lines,
    write_cursor,
)

# ---------------------------------------------------------------------------
# Cursor-specific helpers
# ---------------------------------------------------------------------------


def project_key_from_cwd(cwd: str) -> str:
    """Convert a filesystem path to Cursor's project key format.

    Cursor uses the workspace path with separators replaced by dashes and
    leading slashes stripped:
    e.g. "C:\\Users\\alice\\project" -> "c-Users-alice-project"
         "/home/user/project" -> "home-user-project"
         "/mnt/c/Users/alice/proj" -> "mnt-c-Users-alice-proj"

    On Windows, the drive colon is stripped and the letter lowercased.
    """
    key = cwd.replace("\\", "-").replace("/", "-").replace(":", "")
    # Strip leading dash(es) from Unix paths (e.g. "/home/..." → "-home-..." → "home-...")
    key = key.lstrip("-")
    if len(key) > 1 and key[0].isupper() and key[1] == "-":
        key = key[0].lower() + key[1:]
    return key


def find_cursor_jsonl(session_id: str, project_key: str, home: Path | None = None) -> Path | None:
    """Return the Path to a Cursor session JSONL file, or None if not found.

    Cursor stores transcripts at:
        ~/.cursor/projects/<project_key>/agent-transcripts/<session_id>/<session_id>.jsonl
    """
    if not session_id:
        return None
    if home is None:
        home = Path.home()

    # Primary path: agent-transcripts/<session_id>/<session_id>.jsonl
    primary = home / ".cursor" / "projects" / project_key / "agent-transcripts" / session_id / f"{session_id}.jsonl"
    if primary.exists():
        return primary

    # Fallback: scan all project directories for the session file
    projects_root = home / ".cursor" / "projects"
    if projects_root.exists():
        for match in projects_root.glob(f"**/agent-transcripts/{session_id}/{session_id}.jsonl"):
            return match
        # Last resort: any file matching the session_id
        for match in projects_root.glob(f"**/{session_id}.jsonl"):
            return match

    return None


def get_parent_session_id(jsonl_path: Path) -> str | None:
    """Return the parent session ID if this is a subagent file.

    Subagent JSONL files live at:
      ~/.cursor/projects/<project>/<parent_session_id>/subagents/<subagent_session_id>.jsonl
    """
    parts = jsonl_path.parts
    if len(parts) >= 3 and parts[-2] == "subagents":
        return parts[-3]
    return None


def push_subagent_sessions(
    parent_session_id: str,
    jsonl_path: Path,
    config: dict,
    cwd: str = "",
    home: Path | None = None,
) -> None:
    """Push incremental lines from any subagent JSONL files under the parent session dir."""
    subagents_dir = jsonl_path.parent / parent_session_id / "subagents"
    if not subagents_dir.is_dir():
        return

    for sub_file in subagents_dir.glob("agent-*.jsonl"):
        agent_id = sub_file.stem[len("agent-") :]
        cursor_key = f"{parent_session_id}__sub__{agent_id}"

        offset, line_count = read_cursor(cursor_key, home=home)
        lines, bytes_read = read_new_lines(sub_file, offset=offset)
        if not lines:
            continue

        new_offset = offset + bytes_read
        payload = _build_cursor_payload(
            session_id=agent_id,
            lines=lines,
            start_offset=line_count,
            hook_event="UserPromptSubmit",
            line_count_before=line_count,
            new_offset=new_offset,
            cwd=cwd,
            parent_session_id=parent_session_id,
        )

        success = post_to_server(
            server_url=config["server_url"],
            access_token=config["access_token"],
            payload=payload,
            config=config,
        )
        if success:
            write_cursor(cursor_key, new_offset, line_count + len(lines), home=home)


def _build_cursor_payload(
    session_id: str,
    lines: list[str],
    start_offset: int,
    hook_event: str,
    line_count_before: int,
    new_offset: int = 0,
    cwd: str = "",
    parent_session_id: str | None = None,
    session_jsonl: Path | None = None,
) -> dict:
    """Build payload and tag with ide=cursor."""
    payload = build_payload(
        session_id=session_id,
        lines=lines,
        start_offset=start_offset,
        hook_event=hook_event,
        line_count_before=line_count_before,
        new_offset=new_offset,
        cwd=cwd,
        parent_session_id=parent_session_id,
        session_jsonl=session_jsonl,
    )
    payload["ide"] = "cursor"
    return payload


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _build_usage_line(event: dict) -> str | None:
    """Build a synthetic JSONL line carrying token usage from the hook payload.

    Cursor's stop event includes input_tokens, output_tokens, cache_read_tokens,
    cache_write_tokens at the top level. We wrap them in the message.usage format
    that the server's _extract_usage_tokens() expects.
    """
    input_tokens = event.get("input_tokens", 0) or 0
    output_tokens = event.get("output_tokens", 0) or 0
    cache_read = event.get("cache_read_tokens", 0) or 0
    cache_write = event.get("cache_write_tokens", 0) or 0

    if not any((input_tokens, output_tokens, cache_read, cache_write)):
        return None

    synthetic = {
        "role": "assistant",
        "message": {
            "content": [],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_write,
            },
            "model": event.get("model", ""),
        },
    }
    return json.dumps(synthetic)


def _debug_log(msg: str, home: Path | None = None) -> None:
    """Temporary debug: log to ~/.observal/cursor_hook_debug.log."""
    if home is None:
        home = Path.home()
    try:
        log_dir = home / ".observal"
        log_dir.mkdir(parents=True, exist_ok=True)
        import datetime

        ts = datetime.datetime.now().isoformat(timespec="seconds")
        with open(log_dir / "cursor_hook_debug.log", "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def main(home: Path | None = None) -> None:
    """Main entry point.  Never raises -- hooks must not break the IDE."""
    try:
        _run(home=home)
    except Exception:
        pass


def _run(home: Path | None = None) -> None:
    raw = sys.stdin.read()

    _debug_log(f"STDIN len={len(raw)} payload={raw[:300]}", home=home)

    try:
        event = json.loads(raw)
    except Exception:
        _debug_log("FAIL: invalid JSON", home=home)
        return

    # Cursor hook payload uses camelCase field names:
    #   event, conversationId, workspacePath
    # Also support snake_case fallbacks for forward-compatibility.
    hook_event = event.get("event", "") or event.get("hook_event_name", "")
    session_id = event.get("conversationId", "") or event.get("conversation_id", "") or event.get("session_id", "")
    transcript_path_str = event.get("transcriptPath", "") or event.get("transcript_path", "")
    # workspacePath is a single string in Cursor; workspace_roots is a legacy list fallback
    workspace_path = event.get("workspacePath", "")
    if not workspace_path:
        workspace_roots = event.get("workspace_roots", [])
        workspace_path = workspace_roots[0] if workspace_roots else event.get("cwd", "")
    cwd = workspace_path

    _debug_log(f"PARSED event={hook_event} session={session_id} cwd={cwd}", home=home)

    if not session_id:
        _debug_log("FAIL: no session_id", home=home)
        return

    config = load_config(home=home)
    if config is None:
        _debug_log("FAIL: no config", home=home)
        return

    # Use transcript_path from payload if available; otherwise fall back to search
    jsonl_path: Path | None = None
    if transcript_path_str:
        candidate = Path(transcript_path_str)
        if candidate.exists():
            jsonl_path = candidate

    if jsonl_path is None:
        project_key = project_key_from_cwd(cwd)
        jsonl_path = find_cursor_jsonl(session_id, project_key, home=home)
        _debug_log(f"SEARCH key={project_key} found={jsonl_path}", home=home)

    if jsonl_path is None:
        _debug_log("FAIL: jsonl not found", home=home)
        return

    parent_session_id = get_parent_session_id(jsonl_path)

    offset, line_count = read_cursor(session_id, home=home)
    lines, bytes_read = read_new_lines(jsonl_path, offset=offset)

    _debug_log(f"READ offset={offset} lines={len(lines)} bytes={bytes_read}", home=home)

    if not lines:
        _debug_log("SKIP: no new lines", home=home)
        return

    # On stop events, Cursor includes session-level token counts in the hook
    # payload. Inject a synthetic usage line so the server can aggregate them.
    if hook_event.lower() == "stop":
        usage_line = _build_usage_line(event)
        if usage_line:
            lines.append(usage_line)

    new_offset = offset + bytes_read
    payload = _build_cursor_payload(
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

    # Optimistically write the cursor BEFORE posting so we don't re-read
    # the same lines if Cursor kills this process mid-POST.
    write_cursor(session_id, new_offset, line_count + len(lines), finalized=False, home=home)

    # Spawn background subprocess for the HTTP POST so the hook returns
    # immediately within Cursor's timeout. The subprocess handles retries
    # and error logging independently.
    _spawn_post(payload, config, session_id, offset, new_offset, home=home)
    _debug_log(f"SPAWNED POST for {len(lines)} lines offset={offset}-{new_offset}", home=home)

    is_stop = hook_event.lower() == "stop"
    if is_stop:
        _spawn_tail_flush(session_id)
    else:
        _spawn_crash_recovery()


def _spawn_post(
    payload: dict,
    config: dict,
    session_id: str,
    offset: int,
    new_offset: int,
    home: Path | None = None,
) -> None:
    """Spawn a detached subprocess to POST the payload to the server.

    Cursor hooks have a short timeout (~10s). Posting large payloads to a
    remote server can exceed this, causing Cursor to kill the process before
    the response arrives. By forking the HTTP call into a background process,
    the hook returns immediately and Cursor stays happy.
    """
    import subprocess

    if home is None:
        home = Path.home()

    # Write payload to a temp file; the subprocess reads and deletes it.
    try:
        payload_dir = home / ".observal" / "pending"
        payload_dir.mkdir(parents=True, exist_ok=True)
        payload_file = payload_dir / f"{session_id}_{offset}_{new_offset}.json"
        payload_file.write_text(
            json.dumps(
                {
                    "payload": payload,
                    "server_url": config["server_url"],
                    "access_token": config["access_token"],
                    "config": config,
                    "session_id": session_id,
                    "offset": offset,
                    "new_offset": new_offset,
                }
            )
        )
    except Exception:
        return

    try:
        subprocess.Popen(
            [sys.executable, "-m", "observal_cli.hooks._cursor_post_worker", str(payload_file)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def _spawn_crash_recovery() -> None:
    """Spawn observal_cli.cmd_reconcile as a detached background process."""
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
    """Spawn a delayed tail-flush subprocess to capture post-Stop lines."""
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
