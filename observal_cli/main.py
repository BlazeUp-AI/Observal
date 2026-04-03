"""Observal CLI — MCP Server & Agent Registry."""
import typer

app = typer.Typer(
    name="observal",
    help="Observal — MCP Server & Agent Registry CLI",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)

# ── Register command groups ──────────────────────────────

from observal_cli.cmd_auth import register_auth, register_config
from observal_cli.cmd_mcp import register_mcp
from observal_cli.cmd_agent import agent_app
from observal_cli.cmd_ops import (
    review_app, telemetry_app, eval_app, admin_app,
    register_dashboard, register_feedback, register_traces,
    register_lifecycle,
)

register_auth(app)
register_config(app)
register_mcp(app)
register_dashboard(app)
register_feedback(app)
register_traces(app)
register_lifecycle(app)

app.add_typer(agent_app, name="agent")
app.add_typer(review_app, name="review")
app.add_typer(telemetry_app, name="telemetry")
app.add_typer(eval_app, name="eval")
app.add_typer(admin_app, name="admin")


if __name__ == "__main__":
    app()
