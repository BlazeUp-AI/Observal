# SPDX-FileCopyrightText: 2026 Aryan Iyappan <aryaniyappan2006@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Cursor IDE hook specification for session JSONL push.

Cursor hooks live in ~/.cursor/hooks.json and fire on two events:
  - beforeSubmitPrompt  (analogous to UserPromptSubmit in Claude Code)
  - stop                (session end)
"""

from __future__ import annotations

import sys
from pathlib import Path

CURSOR_HOOK_EVENTS = ("beforeSubmitPrompt", "stop")

# Parent of the observal_cli package directory
_PKG_ROOT = str(Path(__file__).resolve().parent.parent.parent)


def _python_cmd() -> str:
    """Return python command with PYTHONPATH set if needed."""
    try:
        import importlib.util

        if importlib.util.find_spec("observal_cli") is not None:
            return sys.executable
    except Exception:
        pass
    if sys.platform == "win32":
        return f'set "PYTHONPATH={_PKG_ROOT}" && {sys.executable}'
    return f"PYTHONPATH={_PKG_ROOT} {sys.executable}"


def build_cursor_hooks() -> dict:
    """Build the hooks dict for ~/.cursor/hooks.json.

    Returns a dict mapping each Cursor event name to a list of hook entries,
    ready to be merged into the top-level ``hooks`` object.
    """
    cmd = f"{_python_cmd()} -m observal_cli.hooks.cursor_session_push"
    entry = {"command": cmd, "type": "command"}
    return {event: [entry] for event in CURSOR_HOOK_EVENTS}
