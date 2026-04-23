#!/usr/bin/env python3
"""Gemini CLI stop hook for AfterAgent and SessionEnd events.

Captures the assistant's response text from the hook payload and sends
it to Observal as a Stop event. Unlike Claude Code's stop hook (which
parses transcript JSONL), Gemini CLI provides ``prompt_response``
directly in the AfterAgent payload.

Usage (in ~/.gemini/settings.json):
    {"type": "command", "command": "python3 /abs/path/to/gemini_stop_hook.py"}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_hooks_url() -> str:
    """Read hooks URL from env or config file."""
    url = os.environ.get("OBSERVAL_HOOKS_URL")
    if url:
        return url
    cfg_path = Path.home() / ".observal" / "config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
            server = cfg.get("server_url", "")
            if server:
                return f"{server.rstrip('/')}/api/v1/otel/hooks"
        except Exception:
            pass
    return "http://localhost:8000/api/v1/otel/hooks"


def _post(url: str, payload: dict) -> None:
    """POST payload to the hooks endpoint (fire-and-forget)."""
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    headers: dict[str, str] = {"Content-Type": "application/json"}

    uid = payload.get("user_id") or os.environ.get("OBSERVAL_USER_ID")
    uname = payload.get("user_name") or os.environ.get("OBSERVAL_USERNAME")
    if uid:
        headers["X-Observal-User-Id"] = uid
    if uname:
        headers["X-Observal-Username"] = uname

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


def _inject_user_metadata(payload: dict) -> None:
    """Inject user_id and user_name from ~/.observal/config.json."""
    try:
        cfg_path = Path.home() / ".observal" / "config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            if not payload.get("user_id") and cfg.get("user_id"):
                payload["user_id"] = cfg["user_id"]
            if not payload.get("user_name") and cfg.get("user_name"):
                payload["user_name"] = cfg["user_name"]
    except Exception:
        pass


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print('{"continue":true}')
        return

    payload["service_name"] = "gemini-cli"
    _inject_user_metadata(payload)

    url = _resolve_hooks_url()
    session_id = payload.get("session_id", "")
    hook_event = payload.get("hook_event_name", "")

    # First, forward the raw event (same as generic hook)
    _post(url, payload)

    # Then extract and send assistant response as a separate event
    response_text = ""

    if hook_event == "AfterAgent":
        # AfterAgent provides prompt_response directly
        response_text = payload.get("prompt_response", "")

    if response_text:
        # Truncate to 64KB
        response_text = response_text[:65536]
        stop_event = {
            "hook_event_name": "Stop",
            "session_id": session_id,
            "service_name": "gemini-cli",
            "tool_name": "assistant_response",
            "tool_response": response_text,
            "message_sequence": 1,
            "message_total": 1,
        }
        _inject_user_metadata(stop_event)
        _post(url, stop_event)

    # Gemini CLI requires JSON on stdout to proceed
    print('{"continue":true}')


if __name__ == "__main__":
    main()
