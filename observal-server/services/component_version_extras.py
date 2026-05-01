"""Per-type field validation for component version publishing."""

from __future__ import annotations

from fastapi import HTTPException

# Fields allowed in extra dict per component type
HOOK_FIELDS = {
    "event", "execution_mode", "priority", "handler_type", "handler_config",
    "input_schema", "output_schema", "scope", "tool_filter", "file_pattern",
}

SKILL_FIELDS = {
    "skill_path", "target_agents", "task_type", "triggers", "slash_command",
    "has_scripts", "has_templates", "is_power", "power_md", "mcp_server_config",
    "activation_keywords",
}

PROMPT_FIELDS = {
    "category", "template", "variables", "model_hints", "tags",
}

MCP_FIELDS = {
    "source_url", "source_ref", "resolved_sha",
}

SANDBOX_FIELDS = {
    "source_url", "source_ref", "resolved_sha",
}

REQUIRED_FIELDS: dict[str, set[str]] = {
    "hook": {"event", "handler_type"},
    "skill": {"task_type"},
    "prompt": {"category", "template"},
    "mcp": set(),
    "sandbox": set(),
}

ALLOWED_FIELDS: dict[str, set[str]] = {
    "hook": HOOK_FIELDS,
    "skill": SKILL_FIELDS,
    "prompt": PROMPT_FIELDS,
    "mcp": MCP_FIELDS,
    "sandbox": SANDBOX_FIELDS,
}


def validate_and_extract(component_type: str, extra: dict | None) -> dict:
    """Validate extra fields for a component type and return clean field dict.

    Returns a dict of field_name -> value to set on the version model.
    Raises HTTPException(422) on validation errors.
    """
    allowed = ALLOWED_FIELDS.get(component_type)
    if allowed is None:
        raise HTTPException(status_code=422, detail=f"Unknown component type: {component_type!r}")

    required = REQUIRED_FIELDS.get(component_type, set())

    if not extra:
        if required:
            raise HTTPException(
                status_code=422,
                detail=f"Missing required fields for {component_type}: {', '.join(sorted(required))}",
            )
        return {}

    # Check for unknown fields
    unknown = set(extra.keys()) - allowed
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown fields for {component_type}: {', '.join(sorted(unknown))}",
        )

    # Check required fields
    missing = required - set(extra.keys())
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required fields for {component_type}: {', '.join(sorted(missing))}",
        )

    return {k: v for k, v in extra.items() if k in allowed}
