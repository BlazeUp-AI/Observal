#!/usr/bin/env python3
"""Gemini CLI hook script for non-stop events.

Injects ``service_name: "gemini-cli"`` and Observal user metadata into
the hook payload, then forwards it to the Observal hooks endpoint.

On POST failure, buffers the event locally in SQLite so it can be
retried on the next successful hook delivery.

Usage (in ~/.gemini/settings.json):
    {"type": "command", "command": "python3 /abs/path/to/gemini_hook.py"}
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


def _post(url: str, payload: dict) -> bool:
    """POST payload to the hooks endpoint. Returns True on success."""
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
        return True
    except Exception:
        return False


def _buffer(payload: dict) -> None:
    """Buffer the event locally for later retry."""
    try:
        hook_dir = Path(__file__).resolve().parent
        buffer_script = hook_dir / "buffer_event.py"
        if buffer_script.is_file():
            import subprocess

            subprocess.run(
                [sys.executable, str(buffer_script)],
                input=json.dumps(payload).encode("utf-8"),
                timeout=5,
                capture_output=True,
            )
    except Exception:
        pass


def _flush_buffer(url: str) -> None:
    """Kick off a background flush of buffered events."""
    try:
        hook_dir = Path(__file__).resolve().parent
        flush_script = hook_dir / "flush_buffer.py"
        if flush_script.is_file():
            import subprocess

            subprocess.Popen(
                [sys.executable, str(flush_script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


def _extract_token_usage(payload: dict) -> None:
    """Extract token counts from AfterModel's llm_response.usageMetadata."""
    llm_response = payload.get("llm_response")
    if not isinstance(llm_response, dict):
        return
    usage = llm_response.get("usageMetadata")
    if not isinstance(usage, dict):
        return
    if usage.get("promptTokenCount"):
        payload["input_tokens"] = usage["promptTokenCount"]
    if usage.get("candidatesTokenCount"):
        payload["output_tokens"] = usage["candidatesTokenCount"]
    if usage.get("totalTokenCount"):
        payload["total_tokens"] = usage["totalTokenCount"]


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print('{"continue":true}')
        return

    payload["service_name"] = "gemini-cli"
    _inject_user_metadata(payload)

    hook_event = payload.get("hook_event_name", "")

    # AfterModel fires on EVERY streaming chunk — don't forward them as
    # events (they map to Stop and create noise). Only extract token usage
    # from the final chunk (which has usageMetadata) and send that as a
    # dedicated TokenUsage event.
    if hook_event == "AfterModel":
        _extract_token_usage(payload)
        if not payload.get("input_tokens"):
            # Intermediate chunk with no token data — skip entirely
            print('{"continue":true}')
            return
        # Final chunk: send only token data, not the full model response
        session_id = payload.get("session_id", "")
        token_event = {
            "hook_event_name": "Stop",
            "session_id": session_id,
            "service_name": "gemini-cli",
            "tool_name": "token_usage",
            "input_tokens": str(payload["input_tokens"]),
            "output_tokens": str(payload.get("output_tokens", 0)),
        }
        if payload.get("model"):
            token_event["model"] = payload["model"]
        _inject_user_metadata(token_event)
        url = _resolve_hooks_url()
        _post(url, token_event)
        print('{"continue":true}')
        return

    url = _resolve_hooks_url()

    if _post(url, payload):
        _flush_buffer(url)
    else:
        _buffer(payload)

    # Gemini CLI requires JSON on stdout to proceed
    print('{"continue":true}')


if __name__ == "__main__":
    main()
