from __future__ import annotations

import re

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


def _sanitize_name(name: str) -> str:
    if _SAFE_NAME.match(name):
        return name
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)


def _generate_skill_file(skill_listing, ide: str, scope: str = "project") -> dict | None:
    """Generate an IDE-specific skill file dict with path and content.

    Returns None for monolithic IDEs (gemini, codex, copilot) that inline
    skills into their rules markdown.
    """
    name = _sanitize_name(skill_listing.name)
    desc = getattr(skill_listing, "description", "") or ""
    slash_cmd = getattr(skill_listing, "slash_command", None)

    if ide in ("claude-code", "claude_code"):
        content = f"---\nname: {name}\n"
        if desc:
            content += f'description: "{desc}"\n'
        if slash_cmd:
            content += f"command: /{slash_cmd}\n"
        content += f"---\n\n{desc}\n"
        prefix = "~/.claude" if scope == "user" else ".claude"
        return {"path": f"{prefix}/skills/{name}/SKILL.md", "content": content}

    if ide == "kiro":
        content = f"---\nname: {name}\n"
        if desc:
            content += f'description: "{desc}"\n'
        content += f"---\n\n{desc}\n"
        return {"path": f".kiro/skills/{name}/SKILL.md", "content": content}

    if ide == "cursor":
        prefix = "~/.cursor" if scope == "user" else ".cursor"
        content = f"---\ndescription: {desc}\nalwaysApply: false\n---\n\n# {name}\n\n{desc}\n"
        return {"path": f"{prefix}/rules/{name}.md", "content": content}

    if ide == "vscode":
        content = f"---\ndescription: {desc}\nalwaysApply: false\n---\n\n# {name}\n\n{desc}\n"
        return {"path": f".vscode/rules/{name}.md", "content": content}

    return None


def generate_skill_config(
    skill_listing,
    ide: str,
    server_url: str = "http://localhost:8000",
    scope: str = "project",
) -> dict:
    """Generate config snippet for skill install: telemetry hooks + skill file."""
    skill_id = str(skill_listing.id)
    skill_name = str(skill_listing.name)

    hook_entry = {
        "type": "http",
        "url": f"{server_url}/api/v1/telemetry/hooks",
        "headers": {
            "Authorization": "Bearer $OBSERVAL_ACCESS_TOKEN",
            "X-Observal-Skill-Id": skill_id,
        },
        "timeout": 10,
    }
    if ide == "claude-code":
        hook_entry["allowedEnvVars"] = ["OBSERVAL_ACCESS_TOKEN"]

    config = {
        "hooks": {
            "SessionStart": [{"matcher": "*", "hooks": [hook_entry]}],
            "SessionEnd": [{"matcher": "*", "hooks": [hook_entry]}],
        },
        "skill": {"name": skill_name, "id": skill_id},
        "ide": ide,
        "listing_id": skill_id,
    }

    # For Kiro, also include the skill path for auto-loading
    git_url = getattr(skill_listing, "git_url", None)
    if git_url:
        config["skill"]["git_url"] = git_url
    skill_path = getattr(skill_listing, "skill_path", None)
    if skill_path:
        config["skill"]["skill_path"] = skill_path

    # Generate IDE-specific skill file
    skill_file = _generate_skill_file(skill_listing, ide, scope)
    if skill_file:
        config["skill_file"] = skill_file

    return config
