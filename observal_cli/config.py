import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".observal"
CONFIG_FILE = CONFIG_DIR / "config.json"
ALIASES_FILE = CONFIG_DIR / "aliases.json"

DEFAULTS = {
    "output": "table",
    "color": True,
    "server_url": "",
    "api_key": "",
}


def load() -> dict:
    if CONFIG_FILE.exists():
        return {**DEFAULTS, **json.loads(CONFIG_FILE.read_text())}
    return dict(DEFAULTS)


def save(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = load()
    existing.update(data)
    CONFIG_FILE.write_text(json.dumps(existing, indent=2))


def get_or_exit() -> dict:
    cfg = load()
    if not cfg.get("server_url") or not cfg.get("api_key"):
        import typer
        from rich import print as rprint

        rprint("[red]Not configured.[/red] Run [bold]observal init[/bold] or [bold]observal login[/bold] first.")
        raise typer.Exit(1)
    return cfg


# ── Aliases ──────────────────────────────────────────────


def load_aliases() -> dict[str, str]:
    if ALIASES_FILE.exists():
        return json.loads(ALIASES_FILE.read_text())
    return {}


def save_aliases(aliases: dict[str, str]):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ALIASES_FILE.write_text(json.dumps(aliases, indent=2))


def resolve_alias(name: str) -> str:
    """Resolve an alias like @myserver to its UUID, or return as-is."""
    if name.startswith("@"):
        aliases = load_aliases()
        resolved = aliases.get(name[1:])
        if resolved:
            return resolved
        import typer
        from rich import print as rprint

        rprint(f"[red]Unknown alias: {name}[/red]")
        rprint(f"[dim]Set it with: observal config alias {name[1:]} <id>[/dim]")
        raise typer.Exit(1)
    return name
