import typer
import httpx
from rich import print as rprint
from rich.table import Table
from rich.console import Console
from typing import Optional
from observal_cli import config, client

app = typer.Typer(name="observal", help="Observal MCP Server Registry CLI")
review_app = typer.Typer(help="Admin review commands")
agent_app = typer.Typer(help="Agent registry commands")
telemetry_app = typer.Typer(help="Telemetry commands")
eval_app = typer.Typer(help="Evaluation commands")
admin_app = typer.Typer(help="Admin commands")
app.add_typer(review_app, name="review")
app.add_typer(agent_app, name="agent")
app.add_typer(telemetry_app, name="telemetry")
app.add_typer(eval_app, name="eval")
app.add_typer(admin_app, name="admin")
console = Console()

# ── Phase 1 ──────────────────────────────────────────────


@app.command()
def init():
    """First-run setup: configure server and create admin account."""
    server_url = typer.prompt("Server URL", default="http://localhost:8000")
    admin_email = typer.prompt("Admin email")
    admin_name = typer.prompt("Admin name")
    try:
        r = httpx.post(
            f"{server_url.rstrip('/')}/api/v1/auth/init",
            json={"email": admin_email, "name": admin_name},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        config.save({"server_url": server_url, "api_key": data["api_key"]})
        rprint(f"[green]Initialized! API key saved to {config.CONFIG_FILE}[/green]")
    except httpx.ConnectError:
        rprint("[red]Connection failed. Is the server running?[/red]")
        raise typer.Exit(1)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400 and "already initialized" in e.response.text.lower():
            rprint("[yellow]System already initialized.[/yellow]")
            rprint("Use [bold]observal login[/bold] to authenticate with an existing API key,")
            rprint(f"or reset the database: [dim]cd docker && docker compose down -v && docker compose up -d[/dim]")
            if typer.confirm("Do you have an API key and want to login now?", default=True):
                api_key = typer.prompt("API Key", hide_input=True)
                try:
                    r2 = httpx.get(
                        f"{server_url.rstrip('/')}/api/v1/auth/whoami",
                        headers={"X-API-Key": api_key},
                        timeout=30,
                    )
                    r2.raise_for_status()
                    user = r2.json()
                    config.save({"server_url": server_url, "api_key": api_key})
                    rprint(f"[green]Logged in as {user['name']} ({user['email']})[/green]")
                except (httpx.HTTPStatusError, httpx.ConnectError):
                    rprint("[red]Invalid API key or connection failed.[/red]")
                    raise typer.Exit(1)
        else:
            rprint(f"[red]Error {e.response.status_code}: {e.response.text}[/red]")
            raise typer.Exit(1)
        raise typer.Exit(1)


@app.command()
def login():
    """Login with an existing API key."""
    server_url = typer.prompt("Server URL", default="http://localhost:8000")
    api_key = typer.prompt("API Key", hide_input=True)
    try:
        r = httpx.get(
            f"{server_url.rstrip('/')}/api/v1/auth/whoami",
            headers={"X-API-Key": api_key},
            timeout=30,
        )
        r.raise_for_status()
        user = r.json()
        config.save({"server_url": server_url, "api_key": api_key})
        rprint(f"[green]Logged in as {user['name']} ({user['email']})[/green]")
    except httpx.ConnectError:
        rprint("[red]Connection failed. Is the server running?[/red]")
        raise typer.Exit(1)
    except httpx.HTTPStatusError:
        rprint("[red]Invalid API key or server error.[/red]")
        raise typer.Exit(1)


@app.command()
def whoami():
    """Show current authenticated user."""
    user = client.get("/api/v1/auth/whoami")
    rprint(f"[bold]{user['name']}[/bold] ({user['email']})")
    rprint(f"Role: {user.get('role', 'N/A')}")


# ── Phase 2: MCP ─────────────────────────────────────────


@app.command()
def submit(git_url: str = typer.Argument(..., help="Git repository URL")):
    """Submit an MCP server for review."""
    rprint(f"[dim]Analyzing {git_url}...[/dim]")
    try:
        prefill = client.post("/api/v1/mcps/analyze", {"git_url": git_url})
    except (Exception, SystemExit):
        rprint("[yellow]Could not analyze repo, please fill in details manually[/yellow]")
        prefill = {}

    name = typer.prompt("Name", default=prefill.get("name", ""))
    version = typer.prompt("Version (semver)", default=prefill.get("version", "0.1.0"))
    category = typer.prompt("Category")
    description = typer.prompt("Description", default=prefill.get("description", ""))
    owner = typer.prompt("Owner / Team")

    ide_choices = ["vscode", "cursor", "windsurf", "kiro", "claude_code", "gemini_cli"]
    rprint(f"Available IDEs: {', '.join(ide_choices)}")
    ides_input = typer.prompt("Supported IDEs (comma-separated)")
    supported_ides = [i.strip() for i in ides_input.split(",") if i.strip()]

    setup_instructions = typer.prompt("Setup instructions", default="")
    changelog = typer.prompt("Changelog", default="Initial release")

    result = client.post("/api/v1/mcps/submit", {
        "git_url": git_url,
        "name": name,
        "version": version,
        "category": category,
        "description": description,
        "owner": owner,
        "supported_ides": supported_ides,
        "setup_instructions": setup_instructions,
        "changelog": changelog,
    })
    rprint(f"[green]Submitted! ID: {result['id']} — Status: {result.get('status', 'pending')}[/green]")


@app.command(name="list")
def list_mcps(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search term"),
):
    """List available MCP servers."""
    params = {}
    if category:
        params["category"] = category
    if search:
        params["search"] = search
    data = client.get("/api/v1/mcps", params=params)

    table = Table(title="MCP Servers")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Version")
    table.add_column("Category")
    table.add_column("Owner")
    for item in data:
        table.add_row(str(item["id"]), item["name"], item.get("version", ""), item.get("category", ""), item.get("owner", ""))
    console.print(table)


@app.command()
def show(mcp_id: str = typer.Argument(..., help="MCP server ID")):
    """Show full details of an MCP server."""
    item = client.get(f"/api/v1/mcps/{mcp_id}")
    rprint(f"[bold]{item['name']}[/bold] v{item.get('version', '?')}")
    rprint(f"Category: {item.get('category', 'N/A')}")
    rprint(f"Owner: {item.get('owner', 'N/A')}")
    rprint(f"Description: {item.get('description', '')}")
    rprint(f"IDEs: {', '.join(item.get('supported_ides', []))}")
    rprint(f"Setup: {item.get('setup_instructions', 'N/A')}")
    rprint(f"Git: {item.get('git_url', 'N/A')}")


@app.command()
def install(
    mcp_id: str = typer.Argument(..., help="MCP server ID"),
    ide: str = typer.Option(..., "--ide", help="Target IDE"),
):
    """Get install config for an MCP server."""
    result = client.post(f"/api/v1/mcps/{mcp_id}/install", {"ide": ide})
    rprint(f"[green]Config snippet for {ide}:[/green]")
    rprint(result.get("config_snippet", ""))


# ── Review subcommands ───────────────────────────────────


@review_app.command(name="list")
def review_list():
    """List pending submissions (admin only)."""
    data = client.get("/api/v1/review")
    table = Table(title="Pending Reviews")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Submitted By")
    table.add_column("Status")
    for item in data:
        table.add_row(str(item["id"]), item.get("name", ""), item.get("submitted_by", ""), item.get("status", ""))
    console.print(table)


@review_app.command(name="show")
def review_show(review_id: str = typer.Argument(..., help="Review ID")):
    """Show review details (admin only)."""
    item = client.get(f"/api/v1/review/{review_id}")
    rprint(f"[bold]{item.get('name', '')}[/bold] — Status: {item.get('status', '')}")
    rprint(f"Submitted By: {item.get('submitted_by', 'N/A')}")
    rprint(f"Git URL: {item.get('git_url', 'N/A')}")
    rprint(f"Description: {item.get('description', '')}")


@review_app.command(name="approve")
def review_approve(review_id: str = typer.Argument(..., help="Review ID")):
    """Approve a submission (admin only)."""
    result = client.post(f"/api/v1/review/{review_id}/approve")
    rprint(f"[green]Approved: {result.get('name', review_id)}[/green]")


@review_app.command(name="reject")
def review_reject(
    review_id: str = typer.Argument(..., help="Review ID"),
    reason: str = typer.Option(..., "--reason", "-r", help="Rejection reason"),
):
    """Reject a submission (admin only)."""
    result = client.post(f"/api/v1/review/{review_id}/reject", {"reason": reason})
    rprint(f"[yellow]Rejected: {result.get('name', review_id)}[/yellow]")


# ── Phase 3: Agent subcommands ───────────────────────────


@agent_app.command(name="create")
def agent_create():
    """Create a new agent interactively."""
    name = typer.prompt("Agent name")
    version = typer.prompt("Version", default="1.0.0")
    description = typer.prompt("Description (min 100 chars)")
    owner = typer.prompt("Owner / Team")
    prompt_text = typer.prompt("System prompt (min 50 chars)")
    model_name = typer.prompt("Model name", default="claude-sonnet-4")

    max_tokens = typer.prompt("Max tokens", default="4096")
    temperature = typer.prompt("Temperature", default="0.2")
    model_cfg = {"max_tokens": int(max_tokens), "temperature": float(temperature)}

    ide_choices = ["cursor", "kiro", "claude-code", "gemini-cli"]
    rprint(f"Available IDEs: {', '.join(ide_choices)}")
    ides_input = typer.prompt("Supported IDEs (comma-separated)")
    supported_ides = [i.strip() for i in ides_input.split(",") if i.strip()]

    # MCP server selection
    rprint("[dim]Fetching approved MCP servers...[/dim]")
    try:
        mcps = client.get("/api/v1/mcps")
        if mcps:
            table = Table(title="Available MCP Servers")
            table.add_column("ID", style="dim")
            table.add_column("Name", style="bold")
            for m in mcps:
                table.add_row(str(m["id"]), m["name"])
            console.print(table)
        else:
            rprint("[yellow]No approved MCP servers found.[/yellow]")
    except (Exception, SystemExit):
        mcps = []

    mcp_input = typer.prompt("MCP server IDs (comma-separated, or empty)", default="")
    mcp_ids = [i.strip() for i in mcp_input.split(",") if i.strip()]

    # Goal template
    goal_desc = typer.prompt("Goal template description")
    sections = []
    while True:
        sec_name = typer.prompt("Goal section name (or 'done' to finish)")
        if sec_name.lower() == "done":
            break
        sec_desc = typer.prompt(f"  Description for '{sec_name}'", default="")
        grounding = typer.confirm(f"  Grounding required for '{sec_name}'?", default=False)
        sections.append({"name": sec_name, "description": sec_desc, "grounding_required": grounding})

    if not sections:
        rprint("[red]At least one goal section is required.[/red]")
        raise typer.Exit(1)

    result = client.post("/api/v1/agents", {
        "name": name,
        "version": version,
        "description": description,
        "owner": owner,
        "prompt": prompt_text,
        "model_name": model_name,
        "model_config_json": model_cfg,
        "supported_ides": supported_ides,
        "mcp_server_ids": mcp_ids,
        "goal_template": {"description": goal_desc, "sections": sections},
    })
    rprint(f"[green]Agent created! ID: {result['id']}[/green]")


@agent_app.command(name="list")
def agent_list(search: Optional[str] = typer.Option(None, "--search", "-s")):
    """List active agents."""
    params = {"search": search} if search else {}
    data = client.get("/api/v1/agents", params=params)
    table = Table(title="Agents")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Version")
    table.add_column("Model")
    table.add_column("Owner")
    for item in data:
        table.add_row(str(item["id"]), item["name"], item.get("version", ""), item.get("model_name", ""), item.get("owner", ""))
    console.print(table)


@agent_app.command(name="show")
def agent_show(agent_id: str = typer.Argument(..., help="Agent ID")):
    """Show full agent details."""
    item = client.get(f"/api/v1/agents/{agent_id}")
    rprint(f"[bold]{item['name']}[/bold] v{item.get('version', '?')}")
    rprint(f"Owner: {item.get('owner', 'N/A')}")
    rprint(f"Model: {item.get('model_name', 'N/A')}")
    rprint(f"Description: {item.get('description', '')}")
    rprint(f"IDEs: {', '.join(item.get('supported_ides', []))}")
    rprint(f"Status: {item.get('status', 'N/A')}")
    if item.get("mcp_links"):
        rprint("MCP Servers:")
        for link in item["mcp_links"]:
            rprint(f"  - {link.get('mcp_name', link.get('mcp_listing_id', ''))}")
    if item.get("goal_template"):
        gt = item["goal_template"]
        rprint(f"Goal: {gt.get('description', '')}")
        for sec in gt.get("sections", []):
            grounding = " [grounding required]" if sec.get("grounding_required") else ""
            rprint(f"  - {sec['name']}{grounding}")


@agent_app.command(name="install")
def agent_install(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    ide: str = typer.Option(..., "--ide", help="Target IDE"),
):
    """Get install config for an agent."""
    result = client.post(f"/api/v1/agents/{agent_id}/install", {"ide": ide})
    rprint(f"[green]Config for {ide}:[/green]")
    import json
    rprint(json.dumps(result.get("config_snippet", {}), indent=2))


# ── Phase 4: Telemetry subcommands ───────────────────────


@telemetry_app.command(name="status")
def telemetry_status():
    """Check telemetry data flow status."""
    data = client.get("/api/v1/telemetry/status")
    rprint(f"Status: [green]{data.get('status', 'unknown')}[/green]")
    rprint(f"Tool call events (last hour): {data.get('tool_call_events', 0)}")
    rprint(f"Agent interaction events (last hour): {data.get('agent_interaction_events', 0)}")


@telemetry_app.command(name="test")
def telemetry_test():
    """Send a test telemetry event."""
    result = client.post("/api/v1/telemetry/events", {
        "tool_calls": [{
            "mcp_server_id": "test-mcp",
            "tool_name": "test_tool",
            "status": "success",
            "latency_ms": 42,
            "ide": "test",
        }],
    })
    rprint(f"[green]Test event sent! Ingested: {result.get('ingested', 0)}[/green]")


# ── Phase 5: Dashboard commands ──────────────────────────


@app.command(name="metrics")
def metrics(
    item_id: str = typer.Argument(..., help="MCP or Agent ID"),
    item_type: str = typer.Option("mcp", "--type", "-t", help="mcp or agent"),
):
    """Show metrics for an MCP server or agent."""
    if item_type == "agent":
        data = client.get(f"/api/v1/agents/{item_id}/metrics")
        rprint(f"[bold]Agent Metrics[/bold]")
        rprint(f"  Total interactions: {data.get('total_interactions', 0)}")
        rprint(f"  Total downloads: {data.get('total_downloads', 0)}")
        rprint(f"  Acceptance rate: {(data.get('acceptance_rate') or 0):.1%}")
        rprint(f"  Avg tool calls: {data.get('avg_tool_calls', 0)}")
        rprint(f"  Avg latency: {(data.get('avg_latency_ms') or 0):.0f}ms")
    else:
        data = client.get(f"/api/v1/mcps/{item_id}/metrics")
        rprint(f"[bold]MCP Metrics[/bold]")
        rprint(f"  Total downloads: {data.get('total_downloads', 0)}")
        rprint(f"  Total calls: {data.get('total_calls', 0)}")
        rprint(f"  Error rate: {(data.get('error_rate') or 0):.1%}")
        rprint(f"  Avg latency: {(data.get('avg_latency_ms') or 0):.0f}ms")
        rprint(f"  p50/p90/p99: {data.get('p50_latency_ms', 0)}/{data.get('p90_latency_ms', 0)}/{data.get('p99_latency_ms', 0)}ms")


@app.command(name="overview")
def overview():
    """Show enterprise overview stats."""
    data = client.get("/api/v1/overview/stats")
    rprint(f"[bold]Enterprise Overview[/bold]")
    rprint(f"  MCPs: {data.get('total_mcps', 0)}")
    rprint(f"  Agents: {data.get('total_agents', 0)}")
    rprint(f"  Users: {data.get('total_users', 0)}")
    rprint(f"  Tool calls today: {data.get('total_tool_calls_today', 0)}")
    rprint(f"  Agent interactions today: {data.get('total_agent_interactions_today', 0)}")


# ── Phase 6: Feedback commands ───────────────────────────


@app.command()
def rate(
    listing_id: str = typer.Argument(..., help="MCP or Agent ID"),
    stars: int = typer.Option(..., "--stars", "-s", min=1, max=5, help="Rating 1-5"),
    listing_type: str = typer.Option("mcp", "--type", "-t", help="mcp or agent"),
    comment: Optional[str] = typer.Option(None, "--comment", "-c", help="Optional comment"),
):
    """Rate an MCP server or agent."""
    result = client.post("/api/v1/feedback", {
        "listing_id": listing_id,
        "listing_type": listing_type,
        "rating": stars,
        "comment": comment,
    })
    rprint(f"[green]Rated {stars}/5 ✓[/green]")


@app.command()
def feedback(
    listing_id: str = typer.Argument(..., help="MCP or Agent ID"),
    listing_type: str = typer.Option("mcp", "--type", "-t", help="mcp or agent"),
):
    """Show feedback for an MCP server or agent."""
    data = client.get(f"/api/v1/feedback/{listing_type}/{listing_id}")
    if not data:
        rprint("[dim]No feedback yet.[/dim]")
        return
    summary = client.get(f"/api/v1/feedback/summary/{listing_id}")
    rprint(f"[bold]Average: {summary.get('average_rating', 0):.1f}/5 ({summary.get('total_reviews', 0)} reviews)[/bold]")
    for fb in data:
        stars = "★" * fb.get("rating", 0) + "☆" * (5 - fb.get("rating", 0))
        comment = f" — {fb['comment']}" if fb.get("comment") else ""
        rprint(f"  {stars}{comment}")


# ── Phase 7: Eval commands ───────────────────────────────


@eval_app.command(name="run")
def eval_run(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    trace_id: Optional[str] = typer.Option(None, "--trace", help="Specific trace ID"),
):
    """Run evaluation on an agent's traces."""
    body = {}
    if trace_id:
        body["trace_id"] = trace_id
    result = client.post(f"/api/v1/eval/agents/{agent_id}", body)
    rprint(f"[bold]Eval Run: {result.get('id', 'N/A')}[/bold]")
    rprint(f"  Status: {result.get('status', 'N/A')}")
    rprint(f"  Traces evaluated: {result.get('traces_evaluated', 0)}")
    for sc in result.get("scorecards", []):
        rprint(f"  Scorecard {sc['id'][:8]}... — Score: {sc['overall_score']}/10 ({sc['overall_grade']})")


@eval_app.command(name="scorecards")
def eval_scorecards(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    version: Optional[str] = typer.Option(None, "--version", "-v"),
):
    """List scorecards for an agent."""
    params = {}
    if version:
        params["version"] = version
    data = client.get(f"/api/v1/eval/agents/{agent_id}/scorecards", params=params)
    table = Table(title="Scorecards")
    table.add_column("ID", style="dim")
    table.add_column("Version")
    table.add_column("Score")
    table.add_column("Grade")
    table.add_column("Bottleneck")
    table.add_column("Date")
    for sc in data:
        table.add_row(
            str(sc["id"])[:8] + "...",
            sc.get("version", ""),
            f"{sc.get('overall_score', 0):.1f}",
            sc.get("overall_grade", ""),
            sc.get("bottleneck", ""),
            sc.get("evaluated_at", "")[:19],
        )
    console.print(table)


@eval_app.command(name="show")
def eval_show(scorecard_id: str = typer.Argument(..., help="Scorecard ID")):
    """Show scorecard details."""
    sc = client.get(f"/api/v1/eval/scorecards/{scorecard_id}")
    rprint(f"[bold]Scorecard {sc['id']}[/bold]")
    rprint(f"  Overall: {sc.get('overall_score', 0):.1f}/10 ({sc.get('overall_grade', '')})")
    rprint(f"  Bottleneck: {sc.get('bottleneck', 'N/A')}")
    rprint(f"  Recommendations: {sc.get('recommendations', 'N/A')}")
    rprint(f"  Dimensions:")
    for dim in sc.get("dimensions", []):
        score = dim.get('score', 0) or 0
        rprint(f"    {dim.get('dimension', '?')}: {score:.1f}/10 ({dim.get('grade', '?')}) — {dim.get('notes', '')}")


@eval_app.command(name="compare")
def eval_compare(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    version_a: str = typer.Option(..., "--a", help="Version A"),
    version_b: str = typer.Option(..., "--b", help="Version B"),
):
    """Compare two agent versions."""
    data = client.get(f"/api/v1/eval/agents/{agent_id}/compare", params={"version_a": version_a, "version_b": version_b})
    a = data.get("version_a", {})
    b = data.get("version_b", {})
    rprint(f"[bold]Version Comparison[/bold]")
    rprint(f"  {a.get('version', '?')}: avg {a.get('avg_score', 0):.1f}/10 ({a.get('count', 0)} scorecards)")
    rprint(f"  {b.get('version', '?')}: avg {b.get('avg_score', 0):.1f}/10 ({b.get('count', 0)} scorecards)")


# ── Phase 8: Admin commands ──────────────────────────────


@admin_app.command(name="settings")
def admin_settings():
    """List enterprise settings."""
    data = client.get("/api/v1/admin/settings")
    table = Table(title="Enterprise Settings")
    table.add_column("Key", style="bold")
    table.add_column("Value")
    for item in data:
        table.add_row(item["key"], item["value"])
    console.print(table)


@admin_app.command(name="set")
def admin_set(
    key: str = typer.Argument(..., help="Setting key"),
    value: str = typer.Argument(..., help="Setting value"),
):
    """Set an enterprise setting."""
    from observal_cli import config as cli_config
    cfg = cli_config.get_or_exit()
    try:
        r = httpx.put(
            f"{cfg['server_url'].rstrip('/')}/api/v1/admin/settings/{key}",
            headers={"X-API-Key": cfg["api_key"]},
            json={"value": value},
            timeout=30,
        )
        if r.status_code == 200:
            rprint(f"[green]Set {key} = {value}[/green]")
        else:
            rprint(f"[red]Error {r.status_code}: {r.text}[/red]")
    except httpx.ConnectError:
        rprint("[red]Connection failed. Is the server running?[/red]")


@admin_app.command(name="users")
def admin_users():
    """List all users."""
    data = client.get("/api/v1/admin/users")
    table = Table(title="Users")
    table.add_column("ID", style="dim")
    table.add_column("Email")
    table.add_column("Name")
    table.add_column("Role")
    for u in data:
        table.add_row(str(u["id"])[:8] + "...", u["email"], u["name"], u["role"])
    console.print(table)


if __name__ == "__main__":
    app()


# ── Phase 10: CLI Updates ────────────────────────────────


@app.command()
def upgrade():
    """Upgrade observal CLI, shim, and proxy to the latest version."""
    import subprocess
    rprint("[dim]Upgrading observal...[/dim]")
    try:
        result = subprocess.run(
            ["uv", "tool", "upgrade", "observal-cli"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            rprint(f"[green]Upgraded successfully![/green]")
            if result.stdout.strip():
                rprint(result.stdout.strip())
        else:
            # Try pip fallback
            result = subprocess.run(
                ["pip", "install", "--upgrade", "observal-cli"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                rprint(f"[green]Upgraded successfully![/green]")
            else:
                rprint(f"[red]Upgrade failed: {result.stderr.strip()}[/red]")
                raise typer.Exit(1)
    except FileNotFoundError:
        rprint("[red]Neither uv nor pip found. Install manually.[/red]")
        raise typer.Exit(1)


@app.command()
def downgrade():
    """Downgrade observal CLI to a previous version."""
    rprint("[yellow]WIP — observal downgrade is not yet implemented.[/yellow]")
    rprint("[dim]Track progress: https://github.com/BlazeUp-AI/Observal/issues/19[/dim]")


@app.command()
def traces(
    trace_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by trace type"),
    mcp_id: Optional[str] = typer.Option(None, "--mcp", help="Filter by MCP ID"),
    agent_id: Optional[str] = typer.Option(None, "--agent", help="Filter by agent ID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
):
    """List recent traces from ClickHouse (via GraphQL)."""
    import json as _json
    variables = {"limit": limit}
    if trace_type:
        variables["traceType"] = trace_type
    if mcp_id:
        variables["mcpId"] = mcp_id
    if agent_id:
        variables["agentId"] = agent_id

    query = """query($traceType: String, $mcpId: String, $agentId: String, $limit: Int) {
        traces(traceType: $traceType, mcpId: $mcpId, agentId: $agentId, limit: $limit) {
            items {
                traceId traceType name mcpId agentId ide startTime
                metrics { totalSpans errorCount toolCallCount }
            }
        }
    }"""
    cfg = config.get_or_exit()
    try:
        r = httpx.post(
            f"{cfg['server_url'].rstrip('/')}/api/v1/graphql",
            json={"query": query, "variables": variables},
            timeout=30,
        )
        r.raise_for_status()
        items = r.json().get("data", {}).get("traces", {}).get("items", [])
    except Exception as e:
        rprint(f"[red]Failed to query traces: {e}[/red]")
        raise typer.Exit(1)

    table = Table(title="Recent Traces")
    table.add_column("Trace ID", style="dim")
    table.add_column("Type")
    table.add_column("Name")
    table.add_column("MCP/Agent")
    table.add_column("IDE")
    table.add_column("Spans")
    table.add_column("Errors")
    table.add_column("Tools")
    for t in items:
        m = t.get("metrics", {})
        ref = t.get("mcpId") or t.get("agentId") or "—"
        table.add_row(
            t["traceId"][:12] + "…",
            t.get("traceType", ""),
            t.get("name", "") or "—",
            ref[:16],
            t.get("ide", "") or "—",
            str(m.get("totalSpans", 0)),
            str(m.get("errorCount", 0)),
            str(m.get("toolCallCount", 0)),
        )
    console.print(table)


@app.command()
def spans(
    trace_id: str = typer.Argument(..., help="Trace ID"),
):
    """List spans for a trace (via GraphQL)."""
    query = """query($traceId: String!) {
        trace(traceId: $traceId) {
            traceId name
            spans {
                spanId type name method latencyMs status
                toolSchemaValid toolsAvailable
            }
        }
    }"""
    cfg = config.get_or_exit()
    try:
        r = httpx.post(
            f"{cfg['server_url'].rstrip('/')}/api/v1/graphql",
            json={"query": query, "variables": {"traceId": trace_id}},
            timeout=30,
        )
        r.raise_for_status()
        trace_data = r.json().get("data", {}).get("trace")
    except Exception as e:
        rprint(f"[red]Failed to query spans: {e}[/red]")
        raise typer.Exit(1)

    if not trace_data:
        rprint(f"[yellow]Trace {trace_id} not found.[/yellow]")
        raise typer.Exit(1)

    rprint(f"[bold]Trace: {trace_data['traceId']}[/bold] — {trace_data.get('name', '')}")

    table = Table(title="Spans")
    table.add_column("Span ID", style="dim")
    table.add_column("Type")
    table.add_column("Name")
    table.add_column("Method")
    table.add_column("Latency")
    table.add_column("Status")
    table.add_column("Schema")
    for s in trace_data.get("spans", []):
        schema = "✓" if s.get("toolSchemaValid") is True else ("✗" if s.get("toolSchemaValid") is False else "—")
        latency = f"{s['latencyMs']}ms" if s.get("latencyMs") else "—"
        status_style = "red" if s.get("status") == "error" else ""
        table.add_row(
            s["spanId"][:12] + "…",
            s.get("type", ""),
            s.get("name", ""),
            s.get("method", "") or "—",
            latency,
            f"[{status_style}]{s.get('status', '')}[/{status_style}]" if status_style else s.get("status", ""),
            schema,
        )
    console.print(table)


if __name__ == "__main__":
    app()
