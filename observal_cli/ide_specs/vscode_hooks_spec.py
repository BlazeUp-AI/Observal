"""VS Code Copilot hook specification."""

from __future__ import annotations

VSCODE_HOOK_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
    "SubagentStart",
    "SubagentStop",
    "Stop",
)
VSCODE_STOP_EVENTS = ("Stop",)


def build_vscode_hooks(hook_script: str, stop_script: str) -> dict:
    """Build the hooks JSON file content for .github/hooks/observal.json."""
    hooks: dict[str, list] = {}
    for event in VSCODE_HOOK_EVENTS:
        if event in VSCODE_STOP_EVENTS:
            hooks[event] = [
                {"type": "command", "command": hook_script},
                {"type": "command", "command": stop_script},
            ]
        else:
            hooks[event] = [{"type": "command", "command": hook_script}]
    return {"hooks": hooks}
