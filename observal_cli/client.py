import logging
import time
from urllib.parse import urlparse, urlunparse

import httpx
import typer
from rich import print as rprint
from rich.console import Console

from observal_cli import config

console = Console(stderr=True)
logger = logging.getLogger(__name__)


def _client() -> tuple[str, dict]:
    cfg = config.get_or_exit()
    return cfg["server_url"].rstrip("/"), {"X-API-Key": cfg["api_key"]}


def _handle_error(e: httpx.HTTPStatusError, path: str = ""):
    """Handle HTTP errors with actionable messages."""
    ct = e.response.headers.get("content-type", "")
    if "application/json" in ct:
        try:
            detail = e.response.json().get("detail", e.response.text)
        except (ValueError, UnicodeDecodeError):
            detail = e.response.text
    else:
        detail = e.response.text
    code = e.response.status_code

    path_info = f" ({path})" if path else ""

    if code == 401:
        rprint(f"[red]Authentication failed{path_info}.[/red]")
        rprint("[dim]  Run [bold]observal auth login[/bold] to re-authenticate.[/dim]")
    elif code == 403:
        rprint(f"[red]Permission denied{path_info}.[/red]")
        rprint("[dim]  This action requires a higher role (admin or super_admin).[/dim]")
    elif code == 404:
        rprint(f"[red]Not found{path_info}.[/red]")
        rprint(
            "[dim]  Check that the resource ID is correct, or use [bold]observal registry mcp list[/bold] to browse.[/dim]"
        )
    elif code == 429:
        rprint(f"[red]Rate limited{path_info}.[/red]")
        retry_after = e.response.headers.get("Retry-After", "a few seconds")
        rprint(f"[dim]  Try again in {retry_after}.[/dim]")
    elif code >= 500:
        rprint(f"[red]Server error {code}{path_info}.[/red]")
        rprint("[dim]  Check server logs or run [bold]observal doctor[/bold] for diagnostics.[/dim]")
    else:
        rprint(f"[red]Error {code}{path_info}:[/red] {detail}")

    raise typer.Exit(code=1)


def _handle_connect():
    """Handle connection errors."""
    cfg = config.load()
    server_url = cfg.get("server_url", "not set")
    rprint("[red]Connection failed.[/red] Cannot reach the Observal server.")
    rprint(f"[dim]  Server URL: {server_url}[/dim]")
    rprint("[dim]  Is the server running? Try [bold]observal doctor[/bold] to diagnose.[/dim]")
    raise typer.Exit(code=1)


def _handle_timeout(path: str = ""):
    """Handle request timeout."""
    timeout = config.get_timeout()
    path_info = f" ({path})" if path else ""
    rprint(f"[red]Request timed out{path_info}.[/red]")
    rprint(f"[dim]  Timeout: {timeout}s. Increase with [bold]OBSERVAL_TIMEOUT[/bold] env var or config.[/dim]")
    rprint("[dim]  Check server health with [bold]observal doctor[/bold].[/dim]")
    raise typer.Exit(code=1)


_MAX_RETRIES = 3
_RETRY_STATUSES = {429, 503, 504}


def _request_with_retry(
    method: str,
    url: str,
    headers: dict,
    *,
    params: dict | None = None,
    json: dict | None = None,
) -> httpx.Response:
    """Execute an HTTP request with retries on 429/503/504 and Retry-After support."""
    timeout = config.get_timeout()
    func = getattr(httpx, method)

    kwargs: dict = {"headers": headers, "timeout": timeout}
    if params is not None:
        kwargs["params"] = params
    if json is not None:
        kwargs["json"] = json

    for attempt in range(_MAX_RETRIES):
        r = func(url, **kwargs)
        if r.status_code not in _RETRY_STATUSES or attempt == _MAX_RETRIES - 1:
            r.raise_for_status()
            return r
        # Honor Retry-After header if present
        retry_after = r.headers.get("Retry-After")
        delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
        safe_url = urlunparse(urlparse(url)._replace(netloc=urlparse(url).hostname or ""))
        logger.debug(f"Retrying {method.upper()} {safe_url} (attempt {attempt + 1}, delay {delay:.1f}s)")
        time.sleep(delay)
    return r  # unreachable but satisfies type checker


def get(path: str, params: dict | None = None) -> dict:
    base, headers = _client()
    try:
        r = _request_with_retry("get", f"{base}{path}", headers, params=params)
        return r.json()
    except httpx.HTTPStatusError as e:
        _handle_error(e, path)
    except httpx.ReadTimeout:
        _handle_timeout(path)
    except httpx.ConnectError:
        _handle_connect()


def post(path: str, json_data: dict | None = None) -> dict:
    base, headers = _client()
    try:
        r = _request_with_retry("post", f"{base}{path}", headers, json=json_data)
        return r.json()
    except httpx.HTTPStatusError as e:
        _handle_error(e, path)
    except httpx.ReadTimeout:
        _handle_timeout(path)
    except httpx.ConnectError:
        _handle_connect()


def put(path: str, json_data: dict | None = None) -> dict:
    base, headers = _client()
    try:
        r = _request_with_retry("put", f"{base}{path}", headers, json=json_data)
        return r.json()
    except httpx.HTTPStatusError as e:
        _handle_error(e, path)
    except httpx.ReadTimeout:
        _handle_timeout(path)
    except httpx.ConnectError:
        _handle_connect()


def delete(path: str) -> dict:
    base, headers = _client()
    try:
        r = _request_with_retry("delete", f"{base}{path}", headers)
        return r.json()
    except httpx.HTTPStatusError as e:
        _handle_error(e, path)
    except httpx.ReadTimeout:
        _handle_timeout(path)
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
