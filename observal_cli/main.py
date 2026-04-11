"""Observal CLI: MCP Server & Agent Registry."""

from typing import Optional

import typer

from observal_cli.cmd_auth import version_callback

# ── Version callback for --version flag ───────────────────


def _version_option(value: bool):
    if value:
        version_callback()
        raise typer.Exit()


app = typer.Typer(
    name="observal",
    help="Observal: MCP Server & Agent Registry CLI",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Show CLI version and exit.",
        callback=_version_option,
        is_eager=True,
    ),
):
    """Observal: MCP Server & Agent Registry CLI"""


# ── Register command groups ──────────────────────────────

from observal_cli.cmd_agent import agent_app
from observal_cli.cmd_auth import auth_app, register_config, register_deprecated_auth
from observal_cli.cmd_doctor import doctor_app
from observal_cli.cmd_hook import register_hook
from observal_cli.cmd_mcp import register_mcp
from observal_cli.cmd_ops import (
    admin_app,
    ops_app,
    register_deprecated_admin,
    register_deprecated_ops,
    register_lifecycle,
)
from observal_cli.cmd_profile import register_use
from observal_cli.cmd_prompt import register_prompt
from observal_cli.cmd_pull import register_pull
from observal_cli.cmd_sandbox import register_sandbox
from observal_cli.cmd_scan import register_scan
from observal_cli.cmd_skill import register_skill

# ── Auth subgroup (new canonical location) ────────────────
app.add_typer(auth_app, name="auth")

# ── Deprecated root-level auth aliases (backward compat) ──
register_deprecated_auth(app)

# ── Primary user workflows (root) ─────────────────────────
register_config(app)
register_mcp(app)
register_skill(app)
register_hook(app)
register_prompt(app)
register_sandbox(app)
register_pull(app)
register_scan(app)
register_use(app)
register_lifecycle(app)

# ── Subgroups ─────────────────────────────────────────────
app.add_typer(agent_app, name="agent")
app.add_typer(ops_app, name="ops")
app.add_typer(admin_app, name="admin")
app.add_typer(doctor_app, name="doctor")

# ── Deprecated root-level ops/admin aliases ───────────────
register_deprecated_ops(app)
register_deprecated_admin(app)


if __name__ == "__main__":
    app()
