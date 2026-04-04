"""Tool registry CLI commands."""

from __future__ import annotations

import json as _json

import typer
from rich import print as rprint
from rich.table import Table

from observal_cli import client, config
from observal_cli.render import console, kv_panel, output_json, relative_time, spinner, status_badge

tool_app = typer.Typer(help="Tool registry commands")


def register_tool(app: typer.Typer):
    app.add_typer(tool_app, name="tool")


@tool_app.command(name="submit")
def tool_submit(
    from_file: str | None = typer.Option(None, "--from-file", "-f", help="Create from JSON file"),
):
    """Submit a new tool for review."""
    if from_file:
        with open(from_file) as f:
            payload = _json.load(f)
    else:
        payload = {
            "name": typer.prompt("Tool name"),
            "version": typer.prompt("Version", default="1.0.0"),
            "description": typer.prompt("Description"),
            "category": typer.prompt("Category"),
            "owner": typer.prompt("Owner"),
            "function_schema": _json.loads(typer.prompt("Function schema (JSON)")),
        }
    with spinner("Submitting tool..."):
        result = client.post("/api/v1/tools", payload)
    rprint(f"[green]✓ Tool submitted![/green] ID: [bold]{result['id']}[/bold]")


@tool_app.command(name="list")
def tool_list(
    category: str | None = typer.Option(None, "--category", "-c"),
    search: str | None = typer.Option(None, "--search", "-s"),
    output: str = typer.Option("table", "--output", "-o", help="Output: table, json, plain"),
):
    """List approved tools."""
    params = {}
    if category:
        params["category"] = category
    if search:
        params["search"] = search
    with spinner("Fetching tools..."):
        data = client.get("/api/v1/tools", params=params)
    if not data:
        rprint("[dim]No tools found.[/dim]")
        return
    config.save_last_results(data)
    if output == "json":
        output_json(data)
        return
    if output == "plain":
        for item in data:
            rprint(f"{item['id']}  {item['name']}  v{item.get('version', '?')}")
        return
    table = Table(title=f"Tools ({len(data)})", show_lines=False, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Version", style="green")
    table.add_column("Owner", style="dim")
    table.add_column("Status")
    table.add_column("ID", style="dim", max_width=12)
    for i, item in enumerate(data, 1):
        table.add_row(
            str(i), item["name"], item.get("version", ""), item.get("owner", ""),
            status_badge(item.get("status", "")), str(item["id"])[:8] + "…",
        )
    console.print(table)


@tool_app.command(name="show")
def tool_show(
    tool_id: str = typer.Argument(..., help="ID, name, row number, or @alias"),
    output: str = typer.Option("table", "--output", "-o"),
):
    """Show tool details."""
    resolved = config.resolve_alias(tool_id)
    with spinner():
        item = client.get(f"/api/v1/tools/{resolved}")
    if output == "json":
        output_json(item)
        return
    console.print(kv_panel(
        f"{item['name']} v{item.get('version', '?')}",
        [
            ("Status", status_badge(item.get("status", ""))),
            ("Category", item.get("category", "N/A")),
            ("Owner", item.get("owner", "N/A")),
            ("Description", item.get("description", "")),
            ("Created", relative_time(item.get("created_at"))),
            ("ID", f"[dim]{item['id']}[/dim]"),
        ],
        border_style="blue",
    ))


@tool_app.command(name="install")
def tool_install(
    tool_id: str = typer.Argument(..., help="Tool ID, name, row number, or @alias"),
    ide: str = typer.Option(..., "--ide", "-i", help="Target IDE"),
    raw: bool = typer.Option(False, "--raw", help="Output raw JSON only"),
):
    """Get install config for a tool."""
    resolved = config.resolve_alias(tool_id)
    with spinner(f"Generating {ide} config..."):
        result = client.post(f"/api/v1/tools/{resolved}/install", {"ide": ide})
    snippet = result.get("config_snippet", result)
    if raw:
        print(_json.dumps(snippet, indent=2))
        return
    rprint(f"\n[bold]Config for {ide}:[/bold]\n")
    console.print_json(_json.dumps(snippet, indent=2))


@tool_app.command(name="delete")
def tool_delete(
    tool_id: str = typer.Argument(..., help="ID, name, row number, or @alias"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a tool."""
    resolved = config.resolve_alias(tool_id)
    if not yes:
        with spinner():
            item = client.get(f"/api/v1/tools/{resolved}")
        if not typer.confirm(f"Delete [bold]{item['name']}[/bold] ({resolved})?"):
            raise typer.Abort()
    with spinner("Deleting..."):
        client.delete(f"/api/v1/tools/{resolved}")
    rprint(f"[green]✓ Deleted {resolved}[/green]")
