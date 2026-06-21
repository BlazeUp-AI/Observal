# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Antigravity CLI server-side config generator."""

from __future__ import annotations

from loguru import logger

from schemas.ide_registry import IDE_REGISTRY
from services.ide import ConfigContext, register_adapter


class AntigravityAdapter:
    """Antigravity CLI IDE adapter for agent config generation."""

    @property
    def ide_name(self) -> str:
        return "antigravity"

    def format_config(self, ctx: ConfigContext) -> dict:
        logger.debug("format_config: agent={}", ctx.safe_name)
        spec = IDE_REGISTRY["antigravity"]
        options = ctx.options
        scope = options.get("scope", spec["default_scope"])
        desc = (getattr(ctx.agent, "description", "") or ctx.safe_name).replace("\n", " ").strip()[:200]

        result: dict = {
            "agent_file": {
                "path": f"~/.gemini/antigravity-cli/agents/{ctx.safe_name}/agent.json",
                "content": {
                    "name": ctx.safe_name,
                    "description": desc,
                    "system_prompt": ctx.rules_content,
                    "enable_mcp_tools": True,
                    "enable_write_tools": True,
                    "enable_subagent_tools": True,
                },
            },
            "scope": scope,
        }

        if ctx.mcp_configs:
            mcp_path = spec["mcp_config_path"].get(scope, spec["mcp_config_path"]["user"])
            result["mcp_config"] = {"path": mcp_path, "content": {spec["mcp_servers_key"]: ctx.mcp_configs}}

        skill_files = []
        skill_path_template = spec["skill_file"].get(scope, spec["skill_file"]["user"])
        for skill in ctx.skill_configs:
            skill_name = skill.get("name", "unnamed")
            skill_path = skill_path_template.replace("{name}", skill_name)
            skill_files.append({"path": skill_path, "content": skill.get("content", "")})
        if skill_files:
            result["skill_files"] = skill_files

        warnings = list(ctx.compatibility_warnings)
        warnings.extend(options.get("_model_warnings") or [])
        if warnings:
            result["_warnings"] = warnings

        return result


register_adapter(AntigravityAdapter())
