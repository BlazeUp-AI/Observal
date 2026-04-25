"""Copilot CLI hook specification."""

from __future__ import annotations

import sys

COPILOT_CLI_HOOK_EVENTS = (
    "sessionStart",
    "userPromptSubmitted",
    "preToolUse",
    "postToolUse",
    "sessionEnd",
    "errorOccurred",
)
COPILOT_CLI_STOP_EVENTS = ("sessionEnd",)


def build_copilot_cli_hook_entry(hooks_url: str, event: str, is_stop: bool = False) -> dict:
    """Build a single Copilot CLI hook entry for a given event."""
    module = "observal_cli.hooks.copilot_cli_stop_hook" if is_stop else "observal_cli.hooks.copilot_cli_hook"
    cmd = f"{sys.executable} -m {module} --url {hooks_url} --event-name {event}"
    return {"type": "command", "bash": cmd, "powershell": cmd, "timeoutSec": 10}


def build_copilot_cli_hooks(hooks_url: str) -> dict:
    """Build desired hooks for ~/.copilot/config.json."""
    return {
        event: [build_copilot_cli_hook_entry(hooks_url, event, is_stop=(event in COPILOT_CLI_STOP_EVENTS))]
        for event in COPILOT_CLI_HOOK_EVENTS
    }
