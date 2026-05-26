# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""GitHub Copilot CLI IDE adapter."""

from __future__ import annotations

import json
from pathlib import Path

from observal_cli.ide import (
    DiscoveredMcp,
    HookSpec,
    ScanResult,
    register_adapter,
)
from observal_cli.ide.base import BaseAdapter
from observal_cli.shared.utils import _OBSERVAL_HOOK_MARKERS


class CopilotCliAdapter(BaseAdapter):
    """Adapter for GitHub Copilot CLI."""

    @property
    def ide_name(self) -> str:
        return "copilot-cli"

    def scan_home(self, home: Path | None = None) -> ScanResult:
        home = home or Path.home()
        copilot_dir = home / ".copilot"
        if not copilot_dir.exists():
            return ScanResult()
        mcp_file = copilot_dir / "mcp-config.json"
        if not mcp_file.exists():
            return ScanResult()
        try:
            data = json.loads(mcp_file.read_text())
            servers = data.get("mcpServers", {})
            mcps = []
            for srv_name, srv_config in servers.items():
                if isinstance(srv_config, dict):
                    mcps.append(
                        DiscoveredMcp(
                            name=srv_name,
                            command=srv_config.get("command"),
                            args=srv_config.get("args", []),
                            url=srv_config.get("url"),
                            description=f"Copilot CLI MCP: {srv_name}",
                            source="copilot-cli:global",
                        )
                    )
            return ScanResult(mcps=mcps)
        except (json.JSONDecodeError, OSError):
            return ScanResult()

    def scan_project(self, project_dir: Path) -> ScanResult:
        mcp_file = project_dir / ".mcp.json"
        if not mcp_file.exists():
            return ScanResult()
        try:
            data = json.loads(mcp_file.read_text())
            servers = data.get("mcpServers", {})
            mcps = []
            for name, cfg in servers.items():
                if isinstance(cfg, dict):
                    mcps.append(
                        DiscoveredMcp(
                            name=name,
                            command=cfg.get("command"),
                            args=cfg.get("args", []),
                            url=cfg.get("url"),
                            description=f"Copilot CLI project MCP: {name}",
                            source="copilot-cli:project",
                        )
                    )
            return ScanResult(mcps=mcps)
        except (json.JSONDecodeError, OSError):
            return ScanResult()

    def get_hook_spec(self) -> HookSpec:
        return HookSpec(
            events=["SessionStart", "SessionEnd", "ToolUse"],
            format="command",
            markers=["observal", "OBSERVAL"],
        )

    def detect_hooks(self, config_dir: Path) -> str:
        config = config_dir / "config.json"
        if not config.exists():
            return "missing"
        try:
            data = json.loads(config.read_text())
        except (json.JSONDecodeError, OSError):
            return "missing"
        hooks = data.get("hooks", {})
        if not hooks:
            return "missing"
        for _evt, entries in hooks.items():
            if isinstance(entries, list):
                for h in entries:
                    if isinstance(h, dict) and any(
                        m in h.get("bash", "") or m in h.get("command", "") for m in _OBSERVAL_HOOK_MARKERS
                    ):
                        return "installed"
        return "missing"

    def shim_status(self, mcps: list[DiscoveredMcp]) -> str:
        return super().shim_status(mcps)


register_adapter(CopilotCliAdapter())
