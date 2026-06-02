# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Codex CLI IDE adapter."""

from __future__ import annotations

from pathlib import Path

from observal_cli.ide import (
    DiscoveredMcp,
    ScanResult,
    register_adapter,
)
from observal_cli.ide.base import BaseAdapter


def _load_toml(path: Path) -> dict:
    """Load a TOML file with graceful fallback across parser implementations."""
    try:
        import tomllib as toml

        return toml.loads(path.read_text())
    except ImportError:
        pass
    try:
        import tomli as toml  # type: ignore[no-redef]

        return toml.loads(path.read_text())
    except ImportError:
        pass
    try:
        import toml  # type: ignore[no-redef]

        return toml.loads(path.read_text())  # type: ignore[arg-type]
    except ImportError:
        return {}


class CodexAdapter(BaseAdapter):
    """Adapter for Codex CLI (OpenAI)."""

    @property
    def ide_name(self) -> str:
        return "codex"

    def scan_home(self, home: Path | None = None) -> ScanResult:
        home = home or Path.home()
        codex_dir = home / ".codex"
        if not codex_dir.exists():
            return ScanResult()
        config_file = codex_dir / "config.toml"
        if not config_file.exists():
            return ScanResult()
        try:
            data = _load_toml(config_file)
            servers = data.get("mcp", {}).get("servers", {})
            mcps = []
            for srv_name, srv_config in servers.items():
                if isinstance(srv_config, dict):
                    mcps.append(
                        DiscoveredMcp(
                            name=srv_name,
                            command=srv_config.get("command"),
                            args=srv_config.get("args", []),
                            url=srv_config.get("url"),
                            description=f"Codex MCP: {srv_name}",
                            source="codex:global",
                        )
                    )
            return ScanResult(mcps=mcps)
        except Exception:
            return ScanResult()

    def scan_project(self, project_dir: Path) -> ScanResult:
        config_file = project_dir / ".codex" / "config.toml"
        if not config_file.exists():
            return ScanResult()
        try:
            data = _load_toml(config_file)
            servers = data.get("mcp", {}).get("servers", {})
            mcps = []
            for srv_name, srv_config in servers.items():
                if isinstance(srv_config, dict):
                    mcps.append(
                        DiscoveredMcp(
                            name=srv_name,
                            command=srv_config.get("command"),
                            args=srv_config.get("args", []),
                            url=srv_config.get("url"),
                            description=f"Codex project MCP: {srv_name}",
                            source="codex:project",
                        )
                    )
            return ScanResult(mcps=mcps)
        except Exception:
            return ScanResult()

    def shim_status(self, mcps: list[DiscoveredMcp]) -> str:
        return super().shim_status(mcps)


register_adapter(CodexAdapter())
