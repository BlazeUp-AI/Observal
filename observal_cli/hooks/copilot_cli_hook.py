#!/usr/bin/env python3
"""Lightweight Copilot CLI hook script for non-stop events.

Reads the hook JSON payload from stdin, injects Observal metadata
(service_name, session_id, user identity), and forwards it to the
Observal hooks endpoint.

Usage (in ~/.copilot/config.json hooks):
    Unix:    cat | python3 /path/to/copilot_cli_hook.py --url http://localhost:8000/api/v1/otel/hooks
    Windows: python -m observal_cli.hooks.copilot_cli_hook --url http://localhost:8000/api/v1/otel/hooks
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_hooks_url() -> str:
    """Read hooks URL from config file when no --url is provided."""
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


def main():
    import urllib.request

    url = ""
    model = ""
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--url" and i + 1 < len(args):
            url = args[i + 1]
        elif arg == "--model" and i + 1 < len(args):
            model = args[i + 1]
    if not url:
        url = _resolve_hooks_url()

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    payload.setdefault("service_name", "copilot-cli")

    if not payload.get("session_id"):
        payload["session_id"] = f"copilot-cli-{os.getppid()}"

    # Inject user_id and user_name from Observal config if not already present
    if not payload.get("user_id") or not payload.get("user_name"):
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

    if model:
        payload.setdefault("model", model)

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


if __name__ == "__main__":
    main()
