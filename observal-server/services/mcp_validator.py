import ast
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from git import Repo
from sqlalchemy.ext.asyncio import AsyncSession

from models.mcp import McpListing, McpValidationResult

ALLOWED_SCHEMES = {"https", "http"}
BLOCKED_SCHEMES = {"file", "ftp", "ssh", "git"}


def _validate_git_url(url: str) -> str | None:
    """Returns error message if URL is unsafe, None if OK."""
    try:
        parsed = urlparse(url)
    except Exception:
        return "Invalid URL"
    if parsed.scheme not in ALLOWED_SCHEMES:
        return f"URL scheme '{parsed.scheme}' not allowed. Use https://"
    if not parsed.hostname:
        return "URL has no hostname"
    # Block internal/private IPs
    hostname = parsed.hostname.lower()
    if (
        hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1")
        or hostname.startswith("10.")
        or hostname.startswith("192.168.")
        or hostname.startswith("172.")
    ):
        return "Internal/private URLs not allowed"
    return None


async def run_validation(listing: McpListing, db: AsyncSession):
    tmp_dir = tempfile.mkdtemp(prefix="observal_")
    try:
        # Stage 1: Clone & Inspect
        entry_point = await _clone_and_inspect(listing, db, tmp_dir)
        if not entry_point:
            return

        # Stage 2: Manifest Validation
        await _manifest_validation(listing, db, entry_point)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _clone_and_inspect(listing: McpListing, db: AsyncSession, tmp_dir: str) -> Path | None:
    url_err = _validate_git_url(listing.git_url)
    if url_err:
        db.add(McpValidationResult(listing_id=listing.id, stage="clone_and_inspect", passed=False, details=url_err))
        await db.commit()
        return None
    try:
        Repo.clone_from(listing.git_url, tmp_dir, depth=1)
    except Exception as e:
        db.add(
            McpValidationResult(
                listing_id=listing.id,
                stage="clone_and_inspect",
                passed=False,
                details=f"Failed to clone repo: {e}",
            )
        )
        await db.commit()
        return None

    pattern = re.compile(r"FastMCP\(|@mcp\.server")
    entry_point = None
    for py_file in Path(tmp_dir).rglob("*.py"):
        try:
            content = py_file.read_text(errors="ignore")
            if pattern.search(content):
                entry_point = py_file
                break
        except Exception:
            continue

    if not entry_point:
        listing.fastmcp_validated = False
        db.add(
            McpValidationResult(
                listing_id=listing.id,
                stage="clone_and_inspect",
                passed=False,
                details="No FastMCP server found. Expected FastMCP() or @mcp.server in a .py file.",
            )
        )
        await db.commit()
        return None

    listing.fastmcp_validated = True
    db.add(
        McpValidationResult(
            listing_id=listing.id,
            stage="clone_and_inspect",
            passed=True,
            details=f"Found FastMCP entry point: {entry_point.relative_to(tmp_dir)}",
        )
    )
    await db.commit()
    return entry_point


async def _manifest_validation(listing: McpListing, db: AsyncSession, entry_point: Path):
    issues = []
    tools_found = []

    try:
        tree = ast.parse(entry_point.read_text(errors="ignore"))
    except SyntaxError as e:
        db.add(
            McpValidationResult(
                listing_id=listing.id,
                stage="manifest_validation",
                passed=False,
                details=f"Syntax error in entry point: {e}",
            )
        )
        await db.commit()
        return

    # Extract server name from FastMCP() constructor
    server_name = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "FastMCP"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            server_name = node.args[0].value

    # Find @mcp.tool decorated functions
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        is_tool = any(
            (isinstance(d, ast.Attribute) and d.attr == "tool")
            or (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool")
            for d in node.decorator_list
        )
        if not is_tool:
            continue

        docstring = ast.get_docstring(node) or ""
        # Check params have type annotations (skip 'self' and 'return')
        untyped = [a.arg for a in node.args.args if a.arg != "self" and a.annotation is None]

        tools_found.append(
            {
                "name": node.name,
                "docstring": docstring[:100],
                "has_types": len(untyped) == 0,
            }
        )

        if len(docstring) < 20:
            issues.append(f"Tool '{node.name}' docstring too short ({len(docstring)} chars, need 20+)")
        if untyped:
            issues.append(f"Tool '{node.name}' has untyped params: {', '.join(untyped)}")

    if len(listing.description) < 100:
        issues.append(f"Server description too short ({len(listing.description)} chars, need 100+)")

    if not tools_found:
        issues.append("No @mcp.tool decorated functions found")

    passed = len(issues) == 0
    details = f"Server: {server_name or 'unknown'}, Tools: {len(tools_found)}"
    if issues:
        details += "\nIssues:\n- " + "\n- ".join(issues)

    if not passed:
        listing.fastmcp_validated = False

    db.add(
        McpValidationResult(
            listing_id=listing.id,
            stage="manifest_validation",
            passed=passed,
            details=details,
        )
    )
    await db.commit()


async def analyze_repo(git_url: str) -> dict:
    """Clone and analyze a repo without creating a listing. Returns extracted metadata."""
    url_err = _validate_git_url(git_url)
    if url_err:
        return {"name": "", "description": "", "version": "0.1.0", "tools": []}
    tmp_dir = tempfile.mkdtemp(prefix="observal_analyze_")
    try:
        Repo.clone_from(git_url, tmp_dir, depth=1)

        pattern = re.compile(r"FastMCP\(|@mcp\.server")
        entry_point = None
        for py_file in Path(tmp_dir).rglob("*.py"):
            try:
                if pattern.search(py_file.read_text(errors="ignore")):
                    entry_point = py_file
                    break
            except Exception:
                continue

        if not entry_point:
            return {"name": "", "description": "", "version": "0.1.0", "tools": []}

        tree = ast.parse(entry_point.read_text(errors="ignore"))

        server_name = ""
        server_desc = ""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "FastMCP":
                if node.args and isinstance(node.args[0], ast.Constant):
                    server_name = str(node.args[0].value)
                # Check for description keyword arg
                for kw in node.keywords:
                    if kw.arg == "description" and isinstance(kw.value, ast.Constant):
                        server_desc = str(kw.value.value)

        tools = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            is_tool = any(
                (isinstance(d, ast.Attribute) and d.attr == "tool")
                or (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool")
                for d in node.decorator_list
            )
            if is_tool:
                tools.append({"name": node.name, "docstring": ast.get_docstring(node) or ""})

        return {"name": server_name, "description": server_desc, "version": "0.1.0", "tools": tools}
    except Exception:
        return {"name": "", "description": "", "version": "0.1.0", "tools": []}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
