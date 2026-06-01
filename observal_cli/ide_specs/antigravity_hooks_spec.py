# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Antigravity CLI hook specification for session telemetry push.

Hooks are configured in hooks.json at:
  ~/.gemini/config/hooks.json  (global)
  .agents/hooks.json           (workspace)

Schema:
  {
    "<hook-name>": {
      "<EventName>": [
        {
          "matcher": "<tool-name-or-*>",   # optional, omit to match all
          "hooks": [
            {"type": "command", "command": "<cmd>", "timeout": 30}
          ]
        }
      ]
    }
  }

Events used for telemetry:
  PreInvocation  - fires before each user turn (equivalent to UserPromptSubmit)
  Stop           - fires when the session ends
"""

from __future__ import annotations

import sys
from pathlib import Path

_PKG_ROOT = str(Path(__file__).resolve().parent.parent.parent)

_OBSERVAL_HOOK_NAME = "observal-telemetry"


def _python_cmd() -> str:
    """Return python command, using wsl.exe if running under WSL."""
    import subprocess
    try:
        is_wsl = subprocess.run(["wslpath", "-w", "/"], capture_output=True).returncode == 0
    except Exception:
        is_wsl = False

    if is_wsl:
        return f"wsl.exe {sys.executable}"
    return sys.executable


def build_antigravity_hooks(*_args, **_kwargs) -> dict:
    """Build the hooks.json content for Antigravity CLI telemetry.

    Uses PreInvocation (captures user prompt) and Stop (flushes session).
    Returns the full hooks.json dict — the caller writes it to disk.
    """
    cmd = f"{_python_cmd()} -m observal_cli.hooks.antigravity_session_push"
    return {
        _OBSERVAL_HOOK_NAME: {
            "PreInvocation": [
                {
                    "hooks": [
                        {"type": "command", "command": cmd, "timeout": 30}
                    ]
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {"type": "command", "command": cmd, "timeout": 30}
                    ]
                }
            ],
        }
    }
