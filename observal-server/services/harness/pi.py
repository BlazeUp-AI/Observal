# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Pi harness adapter for agent config generation.

Pi is harness-centric: `observal pull` writes AGENTS.md which becomes pi's
entire system prompt, effectively reconfiguring the whole agent runtime.
MCP servers are written to ~/.pi/agent/mcp.json (read by pi-mcp-adapter).
Skills go to .pi/skills/ or ~/.pi/agent/skills/.
"""

from __future__ import annotations

from loguru import logger as optic

from schemas.harness_registry import HARNESS_REGISTRY
from services.harness import ConfigContext, register_adapter


class PiAdapter:
    """Pi harness adapter - harness-centric config generation."""

    @property
    def harness_name(self) -> str:
        return "pi"

    def format_config(self, ctx: ConfigContext) -> dict:
        """Format config for Pi.

        Pi uses:
        - AGENTS.md (project) or ~/.pi/agent/AGENTS.md (user) for the system prompt
        - .pi/mcp.json or ~/.pi/agent/mcp.json for MCP servers (pi-mcp-adapter)
        - .pi/skills/{name}/SKILL.md for skills
        """
        optic.debug("PiAdapter.format_config: agent={}", ctx.safe_name)
        options = ctx.options
        scope = options.get("scope", HARNESS_REGISTRY["pi"]["default_scope"])

        result: dict = {}

        # ── Rules / Agent file (AGENTS.md) ──
        if ctx.rules_content:
            rules_spec = HARNESS_REGISTRY["pi"]["agent_profile"]
            rules_path = rules_spec.get(scope, rules_spec.get("user", "AGENTS.md"))
            result["agent_profile"] = {
                "path": rules_path,
                "content": ctx.rules_content,
            }

        # ── MCP config (for pi-mcp-adapter) ──
        if ctx.mcp_configs:
            mcp_path_spec = HARNESS_REGISTRY["pi"]["mcp_config"]
            mcp_path = mcp_path_spec.get(scope, mcp_path_spec.get("user"))
            if mcp_path:
                result["mcp_config"] = {
                    "path": mcp_path,
                    "content": {"mcpServers": ctx.mcp_configs},
                }

        # ── Skills ──
        if ctx.skill_configs:
            result["skill_components"] = ctx.skill_configs

        return result


register_adapter(PiAdapter())
