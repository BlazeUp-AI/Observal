# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""VS Code IDE adapter for agent config generation."""

from __future__ import annotations

from schemas.ide_registry import IDE_REGISTRY
from services.ide.helpers import (
    _collect_hook_script_files,
    _generate_skill_file,
    _merge_hook_components_into_config,
    _vscode_copilot_hooks_config,
)
from services.ide import ConfigContext, register_adapter


class VscodeAdapter:
    """VS Code IDE adapter."""

    @property
    def ide_name(self) -> str:
        return "vscode"

    def format_config(self, ctx: ConfigContext) -> dict:
        safe_name = ctx.safe_name
        options = ctx.options
        mcp_configs = ctx.mcp_configs
        rules_content = ctx.rules_content
        hook_configs = ctx.hook_configs
        skill_configs = ctx.skill_configs

        spec = IDE_REGISTRY["vscode"]
        ide_scope = options.get("scope", spec.get("default_scope", "project"))
        rules_paths = spec.get("rules_file", {})
        rules_path = rules_paths.get(ide_scope, next(iter(rules_paths.values()), f".rules/{safe_name}.md"))
        mcp_paths = spec.get("mcp_config_path", {})
        mcp_path = mcp_paths.get(ide_scope, next(iter(mcp_paths.values()), ".mcp.json"))

        skill_files = [_generate_skill_file(s, "vscode", ide_scope) for s in skill_configs]
        skill_files = [f for f in skill_files if f]

        result: dict = {
            "rules_file": {"path": rules_path.format(name=safe_name), "content": rules_content},
            "mcp_config": {"path": mcp_path, "content": {spec.get("mcp_servers_key", "mcpServers"): mcp_configs}},
            "scope": ide_scope,
        }

        # Hooks config
        hooks_content = _vscode_copilot_hooks_config()
        _merge_hook_components_into_config(hooks_content, hook_configs, "vscode")
        result["hooks_config"] = {
            "path": ".github/hooks/observal.json",
            "content": hooks_content,
        }

        # Hook script files
        hook_files = _collect_hook_script_files(hook_configs, ctx.hook_listings, "vscode")
        if hook_files:
            result["hook_files"] = hook_files
        if skill_files:
            result["skill_files"] = skill_files
            result["skill_components"] = [s for s in skill_configs if s.get("git_url")]
        if ctx.compatibility_warnings:
            result["_warnings"] = ctx.compatibility_warnings

        return result


register_adapter(VscodeAdapter())
