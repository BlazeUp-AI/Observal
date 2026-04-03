import time

import httpx
import typer
from rich import print as rprint
from rich.console import Console

from observal_cli import config

console = Console(stderr=True)

_TIMEOUT = 30


def _client() -> tuple[str, dict]:
    cfg = config.get_or_exit()
    return cfg["server_url"].rstrip("/"), {"X-API-Key": cfg["api_key"]}


def _handle_error(e: httpx.HTTPStatusError):
    ct = e.response.headers.get("content-type", "")
    detail = e.response.json().get("detail", e.response.text) if "application/json" in ct else e.response.text
    code = e.response.status_code
    if code == 401:
        rprint("[red]Authentication failed.[/red] Run [bold]observal login[/bold] to re-authenticate.")
    elif code == 403:
        rprint("[red]Permission denied.[/red] This action requires a higher role.")
    elif code == 404:
        rprint("[red]Not found.[/red]")
    else:
        rprint(f"[red]Error {code}:[/red] {detail}")
    raise typer.Exit(code=1)


def _handle_connect():
    rprint("[red]Connection failed.[/red] Is the server running?")
    rprint(f"[dim]Server URL: {config.load().get('server_url', 'not set')}[/dim]")
    raise typer.Exit(code=1)


def get(path: str, params: dict | None = None) -> dict:
    base, headers = _client()
    try:
        r = httpx.get(f"{base}{path}", headers=headers, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        _handle_error(e)
    except httpx.ConnectError:
        _handle_connect()


def post(path: str, json_data: dict | None = None) -> dict:
    base, headers = _client()
    try:
        r = httpx.post(f"{base}{path}", headers=headers, json=json_data, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        _handle_error(e)
    except httpx.ConnectError:
        _handle_connect()


def put(path: str, json_data: dict | None = None) -> dict:
    base, headers = _client()
    try:
        r = httpx.put(f"{base}{path}", headers=headers, json=json_data, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        _handle_error(e)
    except httpx.ConnectError:
        _handle_connect()


def delete(path: str) -> dict:
    base, headers = _client()
    try:
        r = httpx.delete(f"{base}{path}", headers=headers, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        _handle_error(e)
    except httpx.ConnectError:
        _handle_connect()


def health() -> tuple[bool, float]:
    """Check server health. Returns (ok, latency_ms)."""
    cfg = config.load()
    url = cfg.get("server_url", "").rstrip("/")
    if not url:
        return False, 0
    try:
        t0 = time.monotonic()
        r = httpx.get(f"{url}/health", timeout=5)
        latency = (time.monotonic() - t0) * 1000
        return r.status_code == 200, latency
    except Exception:
        return False, 0
