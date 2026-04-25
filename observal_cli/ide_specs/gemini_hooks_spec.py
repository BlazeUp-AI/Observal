"""Gemini CLI hook specification."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

GEMINI_HOOK_EVENTS = {
    "SessionStart",
    "BeforeAgent",
    "AfterAgent",
    "AfterModel",
    "BeforeTool",
    "AfterTool",
    "SessionEnd",
    "Notification",
}
GEMINI_STOP_EVENTS = {"AfterAgent", "SessionEnd"}


def build_gemini_hook_cmd(hook_script: Path) -> str:
    """Build the command string for a Gemini hook script."""
    return f"{sys.executable} {hook_script.resolve().as_posix()}"


def build_gemini_hooks(hook_script: Path, stop_script: Path) -> dict:
    """Build the complete hooks dict for ~/.gemini/settings.json."""
    cmd_entry = [{"hooks": [{"type": "command", "command": build_gemini_hook_cmd(hook_script)}]}]
    stop_entry = [{"hooks": [{"type": "command", "command": build_gemini_hook_cmd(stop_script)}]}]
    return {
        "SessionStart": cmd_entry,
        "BeforeAgent": cmd_entry,
        "AfterAgent": stop_entry,
        "AfterModel": cmd_entry,
        "BeforeTool": cmd_entry,
        "AfterTool": cmd_entry,
        "SessionEnd": stop_entry,
        "Notification": cmd_entry,
    }
