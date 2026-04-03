import re

from models.agent import Agent
from services.config_generator import generate_config

_SAFE_NAME = re.compile(r'^[a-zA-Z0-9_-]+$')


def _sanitize_name(name: str) -> str:
    if _SAFE_NAME.match(name):
        return name
    return re.sub(r'[^a-zA-Z0-9_-]', '-', name)


def _inject_agent_id(mcp_config: dict, agent_id: str):
    """Add OBSERVAL_AGENT_ID env var to all MCP server entries for parent trace grouping."""
    for _name, cfg in mcp_config.items():
        if isinstance(cfg, dict):
            cfg.setdefault("env", {})
            cfg["env"]["OBSERVAL_AGENT_ID"] = agent_id


def generate_agent_config(agent: Agent, ide: str) -> dict:
    """Generate IDE-specific config for an agent, bundling prompt + MCP configs."""
    mcp_configs = {}
    agent_id = str(agent.id)

    # Registry MCPs
    for link in agent.mcp_links:
        listing = link.mcp_listing
        if not listing:
            continue
        cfg = generate_config(listing, ide)
        if ide == "claude-code":
            mcp_configs[listing.name] = cfg
        elif "mcpServers" in cfg:
            mcp_configs.update(cfg["mcpServers"])

    # External MCPs — wrap with shim
    for ext in (agent.external_mcps or []):
        name = _sanitize_name(ext.get("name", ""))
        if not name:
            continue
        cmd = ext.get("command", "npx")
        args = ext.get("args", [])
        if isinstance(args, str):
            args = args.split()
        env = ext.get("env", {})
        ext_mcp_id = ext.get("id", name)

        shim_args = ["--mcp-id", ext_mcp_id, "--", cmd] + args

        if ide == "claude-code":
            mcp_configs[name] = {
                "command": ["claude", "mcp", "add", name, "--", "observal-shim"] + shim_args,
                "type": "shell_command",
            }
        elif ide == "gemini-cli":
            mcp_configs[name] = {"command": "observal-shim", "args": shim_args}
        else:
            mcp_configs[name] = {"command": "observal-shim", "args": shim_args, "env": env}

    # Inject OBSERVAL_AGENT_ID into all MCP configs
    _inject_agent_id(mcp_configs, agent_id)

    if ide == "claude-code":
        setup_commands = [
            c.get("command", []) for c in mcp_configs.values()
            if isinstance(c, dict) and c.get("type") == "shell_command"
        ]
        return {
            "rules_file": {"path": f".claude/rules/{_sanitize_name(agent.name)}.md", "content": agent.prompt},
            "mcp_setup_commands": setup_commands,
        }

    if ide == "kiro":
        return {
            "rules_file": {"path": f".kiro/rules/{_sanitize_name(agent.name)}.md", "content": agent.prompt},
            "mcp_json": {"mcpServers": mcp_configs},
        }

    if ide == "gemini-cli":
        return {
            "rules_file": {"path": "GEMINI.md", "content": agent.prompt},
            "mcp_config": {"mcpServers": mcp_configs},
        }

    return {
        "rules_file": {"path": f".rules/{_sanitize_name(agent.name)}.md", "content": agent.prompt},
        "mcp_config": {"mcpServers": mcp_configs},
    }
