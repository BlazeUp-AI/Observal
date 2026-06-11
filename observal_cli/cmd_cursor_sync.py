# SPDX-License-Identifier: AGPL-3.0-only

"""Sync Cursor agent-transcript JSONL into Observal as sessions.

Cursor writes per-session agent transcripts to:
    ~/.cursor/projects/<project>/agent-transcripts/<session_id>/<session_id>.jsonl

Unlike Claude Code, Cursor does not run Observal hooks, so nothing pushes these
transcripts to the server.  This module discovers them and pushes their lines to
the standard session-ingest endpoint with ``ide="cursor"`` (whose registry entry
maps to the ``claude-code`` session parser).

Two normalizations make Cursor lines parseable by that parser:
  1. ``type`` is set from the top-level ``role`` field (Cursor uses ``role``,
     the claude-code parser dispatches on ``type``).
  2. A synthetic ISO ``timestamp`` is injected per line, spread across the
     file's birth..mtime window (Cursor lines carry no timestamps; without one
     every event would default to the year-2000 sentinel server-side).

Run directly (no compiled-CLI rebuild needed):
    python -m observal_cli.cmd_cursor_sync [--since-hours N] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from observal_cli.hooks.session_push import (
    load_config,
    post_to_server,
    read_cursor,
    write_cursor,
)

# Cursor session_id values are UUIDs; prefix the sync-state key so they never
# collide with Claude Code / Kiro session cursors in the same state file.
_CURSOR_KEY = "cursor:{sid}"


def _cursor_projects_dir(home: Path) -> Path:
    return home / ".cursor" / "projects"


def discover_cursor_sessions(
    since_hours: int = 720,
    home: Path | None = None,
) -> list[tuple[Path, str]]:
    """Return (jsonl_path, session_id) for recently-modified Cursor transcripts.

    Layout: ~/.cursor/projects/<project>/agent-transcripts/<sid>/<sid>.jsonl
    Files older than *since_hours* are skipped.
    """
    if home is None:
        home = Path.home()
    root = _cursor_projects_dir(home)
    cutoff = time.time() - since_hours * 3600
    results: list[tuple[Path, str]] = []
    if not root.exists():
        return results

    for project_dir in root.iterdir():
        transcripts_dir = project_dir / "agent-transcripts"
        if not transcripts_dir.is_dir():
            continue
        for session_dir in transcripts_dir.iterdir():
            if not session_dir.is_dir():
                continue
            for jsonl_file in session_dir.glob("*.jsonl"):
                try:
                    if jsonl_file.stat().st_mtime >= cutoff:
                        results.append((jsonl_file, jsonl_file.stem))
                except OSError:
                    pass
    return results


def _file_window(path: Path) -> tuple[float, float]:
    """Return (birth_time, mtime) for *path*, falling back to ctime for birth."""
    st = path.stat()
    birth = getattr(st, "st_birthtime", None) or st.st_ctime
    mtime = st.st_mtime
    if mtime < birth:  # defensive: clock skew / copied files
        birth = mtime
    return birth, mtime


def _iso(ts: float) -> str:
    """ClickHouse/claude-code-compatible ISO timestamp with millis + Z."""
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _explode_blocks(obj: dict) -> list[dict]:
    """Split one Cursor message into one message per content block.

    Cursor packs an entire turn (text + multiple tool_use/tool_result blocks)
    into a single line, whereas the claude-code classifier emits one event per
    line and returns on the *first* block.  To surface tool calls (which the
    insights engine counts), we fan a multi-block message out into one message
    per block, each carrying a single-element ``content`` list.  Messages with
    string or single-block content pass through unchanged.
    """
    role = obj.get("role") or obj.get("type")
    content = obj.get("message", {}).get("content") if isinstance(obj.get("message"), dict) else None
    if not isinstance(content, list) or len(content) <= 1:
        return [obj]

    out: list[dict] = []
    for block in content:
        out.append({"role": role, "type": role, "message": {"content": [block]}})
    return out


def normalize_lines(raw_lines: list[str], birth: float, mtime: float) -> list[str]:
    """Return JSON strings normalized for the claude-code parser.

    Drops blank/unparseable lines, fans multi-block messages out to one block
    each (so ``tool_use`` blocks become ``tool_call`` events), sets ``type`` from
    ``role``, and injects a synthetic ``timestamp`` spread evenly across the
    birth..mtime window so the session has a realistic start, end, and duration.
    """
    parsed: list[dict] = []
    for ln in raw_lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except (json.JSONDecodeError, ValueError):
            continue
        parsed.extend(_explode_blocks(obj))

    n = len(parsed)
    span = max(mtime - birth, 0.0)
    out: list[str] = []
    for i, obj in enumerate(parsed):
        if "type" not in obj and "role" in obj:
            obj["type"] = obj["role"]
        if "timestamp" not in obj:
            frac = (i / (n - 1)) if n > 1 else 1.0
            obj["timestamp"] = _iso(birth + frac * span)
        out.append(json.dumps(obj))
    return out


def _push_session(
    jsonl_path: Path,
    session_id: str,
    config: dict,
    home: Path | None = None,
    dry_run: bool = False,
    agent_id: str | None = None,
) -> tuple[int, bool]:
    """Normalize and push the new tail of one Cursor transcript.

    Returns (lines_sent, ok).  Incremental: only lines beyond the previously
    synced line_count are sent; the server additionally de-dups by offset/hash.
    """
    key = _CURSOR_KEY.format(sid=session_id)
    _, prev_line_count = read_cursor(key, home=home)

    try:
        raw_lines = jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0, True

    birth, mtime = _file_window(jsonl_path)
    normalized = normalize_lines(raw_lines, birth, mtime)
    total = len(normalized)

    if total <= prev_line_count:
        return 0, True  # nothing new

    tail = normalized[prev_line_count:]
    if dry_run:
        return len(tail), True

    payload = {
        "session_id": session_id,
        "ide": "cursor",
        "agent_id": agent_id,
        "lines": tail,
        "start_offset": prev_line_count,
        "hook_event": "Stop",
        "final": True,
        "total_line_count": total,
    }

    ok = post_to_server(
        server_url=config["server_url"],
        access_token=config["access_token"],
        payload=payload,
        config=config,
    )
    if ok:
        # Byte offset isn't meaningful after normalization; store file size for
        # informational parity and track progress by line_count.
        write_cursor(key, jsonl_path.stat().st_size, total, home=home)
    return len(tail), ok


def sync(
    since_hours: int = 720,
    home: Path | None = None,
    dry_run: bool = False,
    agent_id: str | None = None,
) -> dict:
    """Discover and push all recent Cursor transcripts. Returns a summary dict."""
    if home is None:
        home = Path.home()

    config = load_config(home=home)
    if config is None and not dry_run:
        return {"error": "no Observal config (~/.observal/config.json) or not logged in"}

    sessions = discover_cursor_sessions(since_hours=since_hours, home=home)
    pushed = 0
    lines_sent = 0
    failed = 0
    for jsonl_path, session_id in sessions:
        sent, ok = _push_session(
            jsonl_path, session_id, config or {}, home=home, dry_run=dry_run, agent_id=agent_id
        )
        if not ok:
            failed += 1
            continue
        if sent > 0:
            pushed += 1
            lines_sent += sent

    return {
        "discovered": len(sessions),
        "sessions_pushed": pushed,
        "lines_sent": lines_sent,
        "failed": failed,
        "dry_run": dry_run,
    }


def register_cursor_sync(app) -> None:
    """Register the `observal cursor-sync` command on the given Typer app."""
    import typer

    @app.command(name="cursor-sync")
    def cursor_sync(
        since_hours: int = typer.Option(720, "--since-hours", help="Only sync transcripts modified within N hours (default 720 = 30 days)."),
        dry_run: bool = typer.Option(False, "--dry-run", help="Discover and count without pushing."),
        agent_id: str = typer.Option(None, "--agent-id", help="Attribute sessions to this agent UUID (enables Insights for the agent)."),
    ):
        """Sync Cursor agent transcripts into Observal as sessions.

        Discovers ~/.cursor/projects/<project>/agent-transcripts/<sid>/<sid>.jsonl
        and pushes them to the session-ingest endpoint as ide=cursor, so genuine
        Cursor usage appears on the My Traces sessions page.  Pass --agent-id to
        attribute them to a registered agent so they also feed Insights.
        """
        summary = sync(since_hours=since_hours, dry_run=dry_run, agent_id=agent_id)
        typer.echo(json.dumps(summary, indent=2))
        if summary.get("error") or summary.get("failed"):
            raise typer.Exit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync Cursor transcripts to Observal as sessions.")
    parser.add_argument("--since-hours", type=int, default=720, help="Only sync transcripts modified within N hours (default 720 = 30 days).")
    parser.add_argument("--dry-run", action="store_true", help="Discover and count without pushing.")
    parser.add_argument("--agent-id", default=None, help="Attribute sessions to this agent UUID (enables Insights).")
    args = parser.parse_args(argv)

    summary = sync(since_hours=args.since_hours, dry_run=args.dry_run, agent_id=args.agent_id)
    print(json.dumps(summary, indent=2))
    return 1 if summary.get("error") or summary.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
