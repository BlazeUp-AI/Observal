# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Gemini CLI IDE adapter."""

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
from observal_cli.shared.utils import (
    _OBSERVAL_HOOK_MARKERS,
    extract_mcp_servers,
)


class GeminiCliAdapter(BaseAdapter):
    """Adapter for Gemini CLI (Google)."""

    @property
    def ide_name(self) -> str:
        return "gemini-cli"

    def scan_home(self, home: Path | None = None) -> ScanResult:
        home = home or Path.home()
        gemini_dir = home / ".gemini"
        if not gemini_dir.exists():
            return ScanResult()
        settings_file = gemini_dir / "settings.json"
        if not settings_file.exists():
            return ScanResult()
        try:
            settings = json.loads(settings_file.read_text())
            servers = extract_mcp_servers(settings)
            mcps = []
            for srv_name, srv_config in servers.items():
                mcps.append(
                    DiscoveredMcp(
                        name=srv_name,
                        command=srv_config.get("command"),
                        args=srv_config.get("args", []),
                        url=srv_config.get("url"),
                        description=f"Gemini MCP: {srv_name}",
                        source="gemini:global",
                    )
                )
            return ScanResult(mcps=mcps)
        except (json.JSONDecodeError, OSError):
            return ScanResult()

    def scan_project(self, project_dir: Path) -> ScanResult:
        mcp_file = project_dir / ".gemini" / "settings.json"
        if not mcp_file.exists():
            return ScanResult()
        try:
            data = json.loads(mcp_file.read_text())
            servers = extract_mcp_servers(data)
            mcps = []
            for name, cfg in servers.items():
                mcps.append(
                    DiscoveredMcp(
                        name=name,
                        command=cfg.get("command"),
                        args=cfg.get("args", []),
                        url=cfg.get("url"),
                        description=f"Gemini project MCP: {name}",
                        source="gemini-cli:project",
                    )
                )
            return ScanResult(mcps=mcps)
        except (json.JSONDecodeError, OSError):
            return ScanResult()

    def get_hook_spec(self) -> HookSpec:
        return HookSpec(
            events=["PreToolUse", "PostToolUse", "Stop"],
            format="command",
            markers=["observal", "OBSERVAL"],
        )

    def detect_hooks(self, config_dir: Path) -> str:
        settings = config_dir / "settings.json"
        if not settings.exists():
            return "missing"
        try:
            data = json.loads(settings.read_text())
        except (json.JSONDecodeError, OSError):
            return "missing"
        hooks = data.get("hooks", {})
        if not hooks:
            return "missing"
        for _evt, groups in hooks.items():
            if not isinstance(groups, list):
                continue
            for g in groups:
                for h in g.get("hooks", []):
                    if any(m in h.get("command", "") for m in _OBSERVAL_HOOK_MARKERS):
                        return "installed"
        return "missing"

    def shim_status(self, mcps: list[DiscoveredMcp]) -> str:
        return super().shim_status(mcps)


register_adapter(GeminiCliAdapter())
