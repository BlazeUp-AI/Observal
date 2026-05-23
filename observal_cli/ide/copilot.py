# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""GitHub Copilot IDE adapter."""

from __future__ import annotations

import json
from pathlib import Path

from observal_cli.ide import (
    DiscoveredMcp,
    ScanResult,
    register_adapter,
)
from observal_cli.ide.base import BaseAdapter


class CopilotAdapter(BaseAdapter):
    """Adapter for GitHub Copilot (VS Code based)."""

    @property
    def ide_name(self) -> str:
        return "copilot"

    def scan_home(self, home: Path | None = None) -> ScanResult:
        home = home or Path.home()
        vscode_dir = home / ".vscode"
        if not vscode_dir.exists():
            return ScanResult()
        mcp_file = vscode_dir / "mcp.json"
        if not mcp_file.exists():
            return ScanResult()
        try:
            data = json.loads(mcp_file.read_text())
            servers = data.get("servers", data.get("mcpServers", {}))
            mcps = []
            for srv_name, srv_config in servers.items():
                if isinstance(srv_config, dict):
                    mcps.append(
                        DiscoveredMcp(
                            name=srv_name,
                            command=srv_config.get("command"),
                            args=srv_config.get("args", []),
                            url=srv_config.get("url"),
                            description=f"Copilot MCP: {srv_name}",
                            source="copilot:global",
                        )
                    )
            return ScanResult(mcps=mcps)
        except (json.JSONDecodeError, OSError):
            return ScanResult()

    def scan_project(self, project_dir: Path) -> ScanResult:
        mcp_file = project_dir / ".vscode" / "mcp.json"
        if not mcp_file.exists():
            return ScanResult()
        try:
            data = json.loads(mcp_file.read_text())
            servers = data.get("servers", data.get("mcpServers", {}))
            mcps = []
            for name, cfg in servers.items():
                if isinstance(cfg, dict):
                    mcps.append(
                        DiscoveredMcp(
                            name=name,
                            command=cfg.get("command"),
                            args=cfg.get("args", []),
                            url=cfg.get("url"),
                            description=f"Copilot project MCP: {name}",
                            source="copilot:project",
                        )
                    )
            return ScanResult(mcps=mcps)
        except (json.JSONDecodeError, OSError):
            return ScanResult()

    def shim_status(self, mcps: list[DiscoveredMcp]) -> str:
        return super().shim_status(mcps)


register_adapter(CopilotAdapter())
