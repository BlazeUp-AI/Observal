import re

from models.mcp import McpListing

_SAFE_NAME = re.compile(r'^[a-zA-Z0-9_-]+$')


def _sanitize_name(name: str) -> str:
    if _SAFE_NAME.match(name):
        return name
    return re.sub(r'[^a-zA-Z0-9_-]', '-', name)


def generate_config(listing: McpListing, ide: str) -> dict:
    name = _sanitize_name(listing.name)
    mcp_id = str(listing.id)

    # Shim wraps the original command; auth comes from ~/.observal/config.json
    shim_args = ["--mcp-id", mcp_id, "--", "python", "-m", name]

    if ide == "claude-code":
        return {
            "command": ["claude", "mcp", "add", name, "--", "observal-shim"] + shim_args,
            "type": "shell_command",
        }
    if ide == "gemini-cli":
        return {"mcpServers": {name: {"command": "observal-shim", "args": shim_args}}}

    # cursor, vscode, kiro, windsurf, default
    return {"mcpServers": {name: {"command": "observal-shim", "args": shim_args, "env": {}}}}
