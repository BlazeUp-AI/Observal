# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""IDE adapter protocol, context, and registry.

Defines the interface all IDE adapters must implement, the shared
ConfigContext that holds pre-computed data, and the registry that
maps IDE names to adapter instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ConfigContext:
    """Shared pre-computed data passed to each IDE adapter.

    Built once by the orchestrator (generate_agent_config) from the agent
    model and component listings. Adapters use this to format IDE-specific
    output without duplicating the data extraction logic.
    """

    agent: Any  # Agent model instance
    safe_name: str
    ide: str
    observal_url: str
    mcp_configs: dict = field(default_factory=dict)
    rules_content: str = ""
    skill_configs: list = field(default_factory=list)
    hook_configs: list = field(default_factory=list)
    options: dict = field(default_factory=dict)
    platform: str = ""
    compatibility_warnings: list = field(default_factory=list)
    # Optional component listings (passed through for adapters that need them)
    mcp_listings: dict | None = None
    hook_listings: dict | None = None
    skill_listings: dict | None = None
    sandbox_listings: dict | None = None


@runtime_checkable
class IdeAdapter(Protocol):
    """Protocol defining the interface for IDE-specific config generation.

    Each IDE adapter implements this protocol to handle the differences
    in how that IDE expects configuration files to be structured.
    """

    @property
    def ide_name(self) -> str:
        """Canonical IDE name (e.g. 'claude-code', 'cursor')."""
        ...

    def format_config(self, ctx: ConfigContext) -> dict:
        """Format the pre-computed context into IDE-specific config output.

        Returns a dict with IDE-specific keys (rules_file, agent_file,
        mcp_config, hooks_config, etc.).
        """
        ...


# ── Adapter Registry ──────────────────────────────────────────────

_ADAPTER_REGISTRY: dict[str, IdeAdapter] = {}


def register_adapter(adapter: IdeAdapter) -> None:
    """Register an IDE adapter instance."""
    _ADAPTER_REGISTRY[adapter.ide_name] = adapter


def get_adapter(ide: str) -> IdeAdapter | None:
    """Look up an adapter by IDE name or alias. Returns None if not registered."""
    return _ADAPTER_REGISTRY.get(ide) or _ADAPTER_REGISTRY.get(_IDE_ALIASES.get(ide, ""))


# Underscore aliases for backward compatibility
_IDE_ALIASES: dict[str, str] = {
    "claude_code": "claude-code",
    "copilot_cli": "copilot-cli",
}


def get_all_adapters() -> dict[str, IdeAdapter]:
    """Return all registered adapters."""
    return dict(_ADAPTER_REGISTRY)


# ── Orchestrator ──────────────────────────────────────────────────


def generate_agent_config(
    agent: Any,
    ide: str,
    observal_url: str = "http://localhost:8000",
    mcp_listings: dict | None = None,
    component_names: dict | None = None,
    env_values: dict | None = None,
    options: dict | None = None,
    platform: str = "",
    skill_listings: dict | None = None,
    hook_listings: dict | None = None,
    prompt_listings: dict | None = None,
    sandbox_listings: dict | None = None,
) -> dict:
    """Generate IDE-specific config for an agent.

    This is the single entry point for all IDE config generation.
    It builds a shared ConfigContext, resolves the adapter, and delegates.
    """
    import services.ide.load_all  # noqa: F401
    from services.ide.helpers import (
        _build_hook_configs,
        _build_mcp_configs,
        _build_rules_content,
        _build_sandbox_mcp_entry,
        _build_skill_configs,
        _check_ide_compatibility,
        _sanitize_name,
    )

    safe_name = _sanitize_name(agent.name)
    mcp_configs = _build_mcp_configs(agent, ide, observal_url, mcp_listings=mcp_listings, env_values=env_values)

    if sandbox_listings:
        sandbox_mcp = _build_sandbox_mcp_entry(sandbox_listings, ide)
        if sandbox_mcp:
            mcp_configs.update(sandbox_mcp)

    rules_content = _build_rules_content(agent, component_names, prompt_listings, sandbox_listings)
    skill_configs = _build_skill_configs(agent, skill_listings)
    hook_configs = _build_hook_configs(agent, hook_listings)
    options = options or {}
    compatibility_warnings = _check_ide_compatibility(agent, ide)

    adapter = get_adapter(ide)
    if adapter is None:
        raise ValueError(f"No adapter registered for IDE: {ide!r}")

    ctx = ConfigContext(
        agent=agent,
        safe_name=safe_name,
        ide=ide,
        observal_url=observal_url,
        mcp_configs=mcp_configs,
        rules_content=rules_content,
        skill_configs=skill_configs,
        hook_configs=hook_configs,
        options=options,
        platform=platform,
        compatibility_warnings=compatibility_warnings,
        mcp_listings=mcp_listings,
        hook_listings=hook_listings,
        skill_listings=skill_listings,
        sandbox_listings=sandbox_listings,
    )
    return adapter.format_config(ctx)


async def generate_all_ide_configs(
    agent_version: Any,
    agent: Any,
    target_ides: list[str] | None = None,
    observal_url: str = "http://localhost:8000",
    mcp_listings: dict | None = None,
    skill_listings: dict | None = None,
    hook_listings: dict | None = None,
    component_names: dict | None = None,
    env_values: dict | None = None,
) -> dict[str, dict[str, str]]:
    """Generate IDE config files for all target IDEs from an AgentVersion."""
    import json as _json

    from schemas.ide_registry import IDE_REGISTRY

    ides = target_ides or agent_version.supported_ides or list(IDE_REGISTRY.keys())
    result = {}

    for ide in ides:
        if ide not in IDE_REGISTRY:
            continue
        config = generate_agent_config(
            agent=agent,
            ide=ide,
            observal_url=observal_url,
            mcp_listings=mcp_listings,
            skill_listings=skill_listings,
            hook_listings=hook_listings,
            component_names=component_names,
            env_values=env_values,
        )

        files = {}
        if "rules_file" in config:
            rf = config["rules_file"]
            files[rf["path"]] = rf["content"]
        if "agent_file" in config:
            af = config["agent_file"]
            content = af["content"]
            files[af["path"]] = _json.dumps(content, indent=2) if isinstance(content, dict) else content
        if "mcp_config" in config:
            mc = config["mcp_config"]
            if isinstance(mc, dict) and "path" in mc:
                content = mc["content"]
                files[mc["path"]] = _json.dumps(content, indent=2) if isinstance(content, dict) else content
        if "skill_files" in config:
            for sf in config["skill_files"]:
                files[sf["path"]] = sf["content"]

        if files:
            result[ide] = {"files": files}

    return result
