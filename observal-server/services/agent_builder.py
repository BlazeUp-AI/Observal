"""Agent builder — composes resolved components into portable agent manifests.

Generates IDE-specific agent files from a ResolvedAgent:
- Claude Code: .claude/rules/<name>.md (markdown) + MCP JSON config
- Cursor: .cursor/rules/<name>.md (markdown) + .cursor/mcp.json
- Gemini CLI: GEMINI.md (markdown) + MCP JSON config
- Kiro: ~/.kiro/agents/<name>.json (JSON)
- VSCode: .vscode/rules/<name>.md + .vscode/mcp.json
- Codex: AGENTS.md (markdown)
- GitHub Copilot: .github/copilot-instructions.md (markdown)
"""

import logging
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from services.agent_resolver import ResolvedAgent, ResolvedComponent

logger = logging.getLogger(__name__)


# ── Manifest Pydantic Models ────────────────────────────────────────


class ManifestComponent(BaseModel):
    """A single component entry in the agent manifest."""
    name: str
    version: str
    git_url: str
    description: str = ""
    order: int = 0
    git_ref: str | None = None
    config_override: dict | None = None
    # MCP-specific
    transport: str | None = None
    tools: dict | None = None
    # Skill-specific
    slash_command: str | None = None
    task_type: str | None = None
    # Hook-specific
    event: str | None = None
    execution_mode: str | None = None
    priority: int | None = None
    # Prompt-specific
    template: str | None = None
    variables: list[str] | None = None
    # Sandbox-specific
    image: str | None = None
    runtime_type: str | None = None
    resource_limits: dict | None = None

    def model_dump_compact(self) -> dict:
        """Dump only non-None fields for clean manifest output."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class ManifestComponents(BaseModel):
    """All components grouped by type."""
    mcps: list[ManifestComponent] = Field(default_factory=list)
    skills: list[ManifestComponent] = Field(default_factory=list)
    hooks: list[ManifestComponent] = Field(default_factory=list)
    prompts: list[ManifestComponent] = Field(default_factory=list)
    sandboxes: list[ManifestComponent] = Field(default_factory=list)

    def model_dump_compact(self) -> dict:
        """Only include non-empty component lists."""
        result = {}
        for key, items in [
            ("mcps", self.mcps), ("skills", self.skills),
            ("hooks", self.hooks), ("prompts", self.prompts),
            ("sandboxes", self.sandboxes),
        ]:
            if items:
                result[key] = [c.model_dump_compact() for c in items]
        return result


class ManifestError(BaseModel):
    component_type: str
    component_id: str
    reason: str


class AgentManifest(BaseModel):
    """Portable agent manifest — the canonical representation of a composed agent."""
    name: str
    version: str
    components: ManifestComponents = Field(default_factory=ManifestComponents)
    errors: list[ManifestError] = Field(default_factory=list)

    def model_dump_compact(self) -> dict:
        """Clean manifest output (no empty lists, no None values)."""
        result: dict = {
            "name": self.name,
            "version": self.version,
            "components": self.components.model_dump_compact(),
        }
        if self.errors:
            result["errors"] = [e.model_dump() for e in self.errors]
        return result


class CompositionSummary(BaseModel):
    """Lightweight summary of agent composition for API responses."""
    agent_id: str
    agent_name: str
    agent_version: str
    resolved: bool
    component_counts: dict[str, int] = Field(default_factory=dict)
    components: dict[str, list[dict]] = Field(default_factory=dict)
    errors: list[ManifestError] = Field(default_factory=list)


# ── IDE Agent File Models ───────────────────────────────────────────


class AgentFile(BaseModel):
    """A single file to write for IDE agent installation."""
    path: str
    content: str | dict
    format: Literal["markdown", "json", "toml"] = "json"


class IdeAgentConfig(BaseModel):
    """Complete IDE-specific agent configuration output."""
    ide: str
    files: list[AgentFile] = Field(default_factory=list)
    mcp_servers: dict = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    setup_commands: list[list[str]] = Field(default_factory=list)


# ── Builder Functions ───────────────────────────────────────────────


def _resolved_to_manifest_component(comp: ResolvedComponent) -> ManifestComponent:
    """Convert a ResolvedComponent to a ManifestComponent."""
    kwargs: dict = {
        "name": comp.name,
        "version": comp.version,
        "git_url": comp.git_url,
        "description": comp.description,
        "order": comp.order_index,
    }
    if comp.git_ref:
        kwargs["git_ref"] = comp.git_ref
    if comp.config_override:
        kwargs["config_override"] = comp.config_override

    # Type-specific fields from extra
    if comp.component_type == "mcp":
        if comp.extra.get("transport"):
            kwargs["transport"] = comp.extra["transport"]
        if comp.extra.get("tools_schema"):
            kwargs["tools"] = comp.extra["tools_schema"]
    elif comp.component_type == "skill":
        if comp.extra.get("slash_command"):
            kwargs["slash_command"] = comp.extra["slash_command"]
        if comp.extra.get("task_type"):
            kwargs["task_type"] = comp.extra["task_type"]
    elif comp.component_type == "hook":
        kwargs["event"] = comp.extra.get("event", "")
        kwargs["execution_mode"] = comp.extra.get("execution_mode", "async")
        kwargs["priority"] = comp.extra.get("priority", 100)
    elif comp.component_type == "prompt":
        if comp.extra.get("template"):
            kwargs["template"] = comp.extra["template"]
        if comp.extra.get("variables"):
            kwargs["variables"] = comp.extra["variables"]
    elif comp.component_type == "sandbox":
        kwargs["image"] = comp.extra.get("image", "")
        kwargs["runtime_type"] = comp.extra.get("runtime_type", "")
        if comp.extra.get("resource_limits"):
            kwargs["resource_limits"] = comp.extra["resource_limits"]

    return ManifestComponent(**kwargs)


def build_agent_manifest(resolved: ResolvedAgent) -> dict:
    """Build a portable agent manifest from a fully resolved agent.

    Returns a clean dict with only populated fields.
    """
    type_map = {
        "mcp": "mcps",
        "skill": "skills",
        "hook": "hooks",
        "prompt": "prompts",
        "sandbox": "sandboxes",
    }

    grouped: dict[str, list[ManifestComponent]] = {}
    for ctype, key in type_map.items():
        typed = resolved.components_by_type(ctype)
        if typed:
            grouped[key] = [_resolved_to_manifest_component(c) for c in typed]

    manifest = AgentManifest(
        name=resolved.agent_name,
        version=resolved.agent_version,
        components=ManifestComponents(**grouped),
        errors=[
            ManifestError(
                component_type=e.component_type,
                component_id=str(e.component_id),
                reason=e.reason,
            )
            for e in resolved.errors
        ],
    )
    return manifest.model_dump_compact()


def build_composition_summary(resolved: ResolvedAgent) -> dict:
    """Build a lightweight summary of the agent's composition for API responses."""
    type_map = {
        "mcp": "mcps",
        "skill": "skills",
        "hook": "hooks",
        "prompt": "prompts",
        "sandbox": "sandboxes",
    }

    component_counts: dict[str, int] = {}
    components_by_key: dict[str, list[dict]] = {}

    for ctype, key in type_map.items():
        typed = resolved.components_by_type(ctype)
        if typed:
            component_counts[ctype] = len(typed)
            components_by_key[key] = [
                {"name": c.name, "version": c.version, "order": c.order_index}
                for c in typed
            ]

    summary = CompositionSummary(
        agent_id=str(resolved.agent_id),
        agent_name=resolved.agent_name,
        agent_version=resolved.agent_version,
        resolved=resolved.ok,
        component_counts=component_counts,
        components=components_by_key,
        errors=[
            ManifestError(
                component_type=e.component_type,
                component_id=str(e.component_id),
                reason=e.reason,
            )
            for e in resolved.errors
        ],
    )
    return summary.model_dump(exclude_none=True)
