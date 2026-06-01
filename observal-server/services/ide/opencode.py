# SPDX-FileCopyrightText: 2026 Lokesh Selvam <lokeshselvam7025@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""OpenCode IDE adapter for agent config generation.

Generates full config when a user installs an agent for OpenCode, including:
- Rules file (agent markdown at .opencode/agents/ or ~/.config/opencode/agents/)
- MCP config (opencode.json with "mcp" key)
- Plugin-based hooks (observal-plugin.ts in .opencode/plugins/)
- Skills (SKILL.md files in .opencode/skills/)
"""

from __future__ import annotations

from loguru import logger as optic

from schemas.ide_registry import IDE_REGISTRY
from services.ide import ConfigContext, register_adapter
from services.ide.helpers import _generate_skill_file


class OpenCodeAdapter:
    """OpenCode IDE adapter."""

    @property
    def ide_name(self) -> str:
        return "opencode"

    def format_config(self, ctx: ConfigContext) -> dict:
        optic.trace("ctx={}", ctx)
        safe_name = ctx.safe_name
        options = ctx.options
        mcp_configs = ctx.mcp_configs
        rules_content = ctx.rules_content
        skill_configs = ctx.skill_configs

        opencode_spec = IDE_REGISTRY["opencode"]
        opencode_scope = options.get("scope", opencode_spec["default_scope"])

        # Build MCP configs in OpenCode's format:
        # { "mcp": { "name": { "type": "local", "command": [...] } } }
        opencode_mcp = {}
        for k, v in mcp_configs.items():
            cmd_array = [v["command"], *v.get("args", [])]
            entry = {"type": "local", "command": cmd_array}
            if v.get("env"):
                entry["environment"] = v["env"]
            opencode_mcp[k] = entry

        rules_path = opencode_spec["rules_file"][opencode_scope].format(name=safe_name)
        mcp_path = opencode_spec["mcp_config_path"].get(
            opencode_scope, next(iter(opencode_spec["mcp_config_path"].values()))
        )

        opencode_content: dict = {opencode_spec["mcp_servers_key"]: opencode_mcp}
        opencode_model = options.get("_resolved_model")
        if opencode_model:
            opencode_content["model"] = opencode_model

        # Generate plugin source for telemetry hooks
        from services.ide.helpers import _opencode_plugin_js

        plugin_source = _opencode_plugin_js()

        result: dict = {
            "rules_file": {"path": rules_path, "content": rules_content},
            "mcp_config": {"path": mcp_path, "content": opencode_content},
            "hooks_config": {
                "path": ".opencode/plugins/observal-plugin.ts",
                "content": plugin_source,
            },
            "scope": opencode_scope,
        }

        # Generate skill files
        if skill_configs:
            skill_components = []
            for skill in skill_configs:
                skill_file = _generate_skill_file(skill, "opencode", opencode_scope)
                if skill_file:
                    skill_components.append(skill_file)
            if skill_components:
                result["skill_components"] = skill_components

        warnings_combined = list(ctx.compatibility_warnings)
        warnings_combined.extend(options.get("_model_warnings") or [])
        if warnings_combined:
            result["_warnings"] = warnings_combined

        return result


register_adapter(OpenCodeAdapter())
