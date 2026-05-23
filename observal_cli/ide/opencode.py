# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""OpenCode IDE adapter."""

from __future__ import annotations

import json
from pathlib import Path

from observal_cli.ide import (
    DiscoveredMcp,
    ScanResult,
    register_adapter,
)
from observal_cli.ide.base import BaseAdapter


class OpenCodeAdapter(BaseAdapter):
    """Adapter for OpenCode."""

    @property
    def ide_name(self) -> str:
        return "opencode"

    def scan_home(self, home: Path | None = None) -> ScanResult:
        home = home or Path.home()
        opencode_dir = home / ".config" / "opencode"
        if not opencode_dir.exists():
            return ScanResult()
        config_file = opencode_dir / "opencode.json"
        if not config_file.exists():
            return ScanResult()
        return self._parse_opencode_config(config_file, "opencode:global")

    def scan_project(self, project_dir: Path) -> ScanResult:
        config_file = project_dir / "opencode.json"
        if not config_file.exists():
            return ScanResult()
        return self._parse_opencode_config(config_file, "opencode:project")

    def shim_status(self, mcps: list[DiscoveredMcp]) -> str:
        return super().shim_status(mcps)

    def _parse_opencode_config(self, config_file: Path, source: str) -> ScanResult:
        """Parse an opencode.json config and extract MCP servers."""
        try:
            data = json.loads(config_file.read_text())
            servers = data.get("mcp", {})
            mcps = []
            for srv_name, srv_config in servers.items():
                if isinstance(srv_config, dict):
                    cmd = srv_config.get("command")
                    if isinstance(cmd, list):
                        command = cmd[0] if cmd else None
                        args = cmd[1:] if len(cmd) > 1 else []
                    else:
                        command = cmd
                        args = srv_config.get("args", [])
                    mcps.append(
                        DiscoveredMcp(
                            name=srv_name,
                            command=command,
                            args=args,
                            url=srv_config.get("url"),
                            description=f"OpenCode MCP: {srv_name}",
                            source=source,
                        )
                    )
            return ScanResult(mcps=mcps)
        except (json.JSONDecodeError, OSError):
            return ScanResult()


register_adapter(OpenCodeAdapter())
