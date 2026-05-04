"""Cursor hook specification."""

from __future__ import annotations

CURSOR_HOOK_EVENTS = (
    "sessionStart",
    "preToolUse",
    "postToolUse",
    "postToolUseFailure",
    "subagentStart",
    "subagentStop",
    "beforeShellExecution",
    "afterShellExecution",
    "afterFileEdit",
    "preCompact",
    "stop",
)
CURSOR_STOP_EVENTS = ("stop",)


def build_cursor_hooks(hook_script: str, stop_script: str) -> dict:
    """Build the complete hooks.json content for Cursor."""
    hooks: dict[str, list] = {}
    for event in CURSOR_HOOK_EVENTS:
        if event in CURSOR_STOP_EVENTS:
            hooks[event] = [
                {"command": hook_script, "type": "command"},
                {"command": stop_script, "type": "command"},
            ]
        else:
            hooks[event] = [{"command": hook_script, "type": "command"}]
    return {"version": 1, "hooks": hooks}
