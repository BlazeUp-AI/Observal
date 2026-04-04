"""GraphRAG registry CLI commands."""

from __future__ import annotations

import json as _json

import typer
from rich import print as rprint
from rich.table import Table

from observal_cli import client, config
from observal_cli.render import console, kv_panel, output_json, relative_time, spinner, status_badge

graphrag_app = typer.Typer(help="GraphRAG registry commands")


def register_graphrag(app: typer.Typer):
    app.add_typer(graphrag_app, name="graphrag")


@graphrag_app.command(name="submit")
def graphrag_submit(
    from_file: str | None = typer.Option(None, "--from-file", "-f", help="Create from JSON file"),
):
    """Submit a new GraphRAG for review."""
    if from_file:
        with open(from_file) as f:
            payload = _json.load(f)
    else:
        payload = {
            "name": typer.prompt("GraphRAG name"),
            "version": typer.prompt("Version", default="1.0.0"),
            "description": typer.prompt("Description"),
            "owner": typer.prompt("Owner"),
            "endpoint_url": typer.prompt("Endpoint URL"),
            "query_interface": typer.prompt("Query interface (graphql/rest/cypher/sparql)"),
            "auth_type": typer.prompt("Auth type"),
        }
    with spinner("Submitting GraphRAG..."):
        result = client.post("/api/v1/graphrags", payload)
    rprint(f"[green]✓ GraphRAG submitted![/green] ID: [bold]{result['id']}[/bold]")


@graphrag_app.command(name="list")
def graphrag_list(
    query_interface: str | None = typer.Option(None, "--query-interface", "-q"),
    search: str | None = typer.Option(None, "--search", "-s"),
    output: str = typer.Option("table", "--output", "-o", help="Output: table, json, plain"),
):
    """List approved GraphRAGs."""
    params = {}
    if query_interface:
        params["query_interface"] = query_interface
    if search:
        params["search"] = search
    with spinner("Fetching GraphRAGs..."):
        data = client.get("/api/v1/graphrags", params=params)
    if not data:
        rprint("[dim]No GraphRAGs found.[/dim]")
        return
    config.save_last_results(data)
    if output == "json":
        output_json(data)
        return
    if output == "plain":
        for item in data:
            rprint(f"{item['id']}  {item['name']}  v{item.get('version', '?')}")
        return
    table = Table(title=f"GraphRAGs ({len(data)})", show_lines=False, padding=(0, 1))
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


@graphrag_app.command(name="show")
def graphrag_show(
    graphrag_id: str = typer.Argument(..., help="ID, name, row number, or @alias"),
    output: str = typer.Option("table", "--output", "-o"),
):
    """Show GraphRAG details."""
    resolved = config.resolve_alias(graphrag_id)
    with spinner():
        item = client.get(f"/api/v1/graphrags/{resolved}")
    if output == "json":
        output_json(item)
        return
    console.print(kv_panel(
        f"{item['name']} v{item.get('version', '?')}",
        [
            ("Status", status_badge(item.get("status", ""))),
            ("Endpoint", item.get("endpoint_url", "N/A")),
            ("Query Interface", item.get("query_interface", "N/A")),
            ("Auth Type", item.get("auth_type", "N/A")),
            ("Owner", item.get("owner", "N/A")),
            ("Description", item.get("description", "")),
            ("Created", relative_time(item.get("created_at"))),
            ("ID", f"[dim]{item['id']}[/dim]"),
        ],
        border_style="magenta",
    ))


@graphrag_app.command(name="install")
def graphrag_install(
    graphrag_id: str = typer.Argument(..., help="GraphRAG ID, name, row number, or @alias"),
    ide: str = typer.Option(..., "--ide", "-i", help="Target IDE"),
    raw: bool = typer.Option(False, "--raw", help="Output raw JSON only"),
):
    """Get install config for a GraphRAG."""
    resolved = config.resolve_alias(graphrag_id)
    with spinner(f"Generating {ide} config..."):
        result = client.post(f"/api/v1/graphrags/{resolved}/install", {"ide": ide})
    snippet = result.get("config_snippet", result)
    if raw:
        print(_json.dumps(snippet, indent=2))
        return
    rprint(f"\n[bold]Config for {ide}:[/bold]\n")
    console.print_json(_json.dumps(snippet, indent=2))


@graphrag_app.command(name="delete")
def graphrag_delete(
    graphrag_id: str = typer.Argument(..., help="ID, name, row number, or @alias"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a GraphRAG."""
    resolved = config.resolve_alias(graphrag_id)
    if not yes:
        with spinner():
            item = client.get(f"/api/v1/graphrags/{resolved}")
        if not typer.confirm(f"Delete [bold]{item['name']}[/bold] ({resolved})?"):
            raise typer.Abort()
    with spinner("Deleting..."):
        client.delete(f"/api/v1/graphrags/{resolved}")
    rprint(f"[green]✓ Deleted {resolved}[/green]")
