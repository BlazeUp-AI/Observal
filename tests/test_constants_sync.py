"""Verify that observal_cli.constants stays in sync with schemas.constants."""

import importlib

import pytest

_SHARED_LISTS = [
    "VALID_IDES",
    "VALID_MCP_CATEGORIES",
    "VALID_MCP_TRANSPORTS",
    "VALID_MCP_FRAMEWORKS",
    "VALID_SKILL_TASK_TYPES",
    "VALID_HOOK_EVENTS",
    "VALID_HOOK_HANDLER_TYPES",
    "VALID_HOOK_EXECUTION_MODES",
    "VALID_HOOK_SCOPES",
    "VALID_PROMPT_CATEGORIES",
    "VALID_SANDBOX_RUNTIME_TYPES",
    "VALID_SANDBOX_NETWORK_POLICIES",
]


@pytest.mark.parametrize("name", _SHARED_LISTS)
def test_constants_match(name):
    server = importlib.import_module("schemas.constants")
    cli = importlib.import_module("observal_cli.constants")
    server_val = getattr(server, name)
    cli_val = getattr(cli, name)
    assert server_val == cli_val, f"{name} mismatch: server={server_val!r}, cli={cli_val!r}"
