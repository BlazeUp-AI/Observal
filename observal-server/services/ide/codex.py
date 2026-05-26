# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Codex CLI IDE adapter for agent config generation."""

from __future__ import annotations

from loguru import logger

from schemas.ide_registry import IDE_REGISTRY
from services.ide import ConfigContext, register_adapter


class CodexAdapter:
    """Codex CLI IDE adapter."""

    @property
    def ide_name(self) -> str:
        logger.debug("ide_name called")
        return "codex"

    def format_config(self, ctx: ConfigContext) -> dict:
        logger.debug("format_config: ctx={}", ctx)
        options = ctx.options
        mcp_configs = ctx.mcp_configs
        rules_content = ctx.rules_content

        codex_spec = IDE_REGISTRY["codex"]
        codex_scope = codex_spec["default_scope"]
        codex_content: dict = {"mcp.servers": mcp_configs}
        codex_model = options.get("_resolved_model")
        if codex_model:
            codex_content["model"] = codex_model

        result: dict = {
            "rules_file": {"path": codex_spec["rules_file"][codex_scope], "content": rules_content},
            "mcp_config": {"path": codex_spec["mcp_config_path"][codex_scope], "content": codex_content},
            "scope": codex_scope,
        }

        warnings_combined = list(ctx.compatibility_warnings)
        warnings_combined.extend(options.get("_model_warnings") or [])
        if warnings_combined:
            result["_warnings"] = warnings_combined

        return result


register_adapter(CodexAdapter())
