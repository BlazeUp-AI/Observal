# SPDX-FileCopyrightText: 2026 Swathi Saravanan <ss4522@cornell.edu>
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for observal-shim wrapping in `observal doctor patch`."""

from __future__ import annotations

import json

from observal_cli.cmd_doctor import _is_already_shimmed, _shim_config_file, _wrap_with_shim


def test_wrap_with_shim_basic():
    wrapped = _wrap_with_shim({"command": "npx", "args": ["-y", "pkg"]}, "my-mcp")
    assert wrapped["command"] == "observal-shim"
    assert wrapped["args"] == ["--mcp-id", "my-mcp", "--", "npx", "-y", "pkg"]


def test_wrap_with_shim_tags_ide():
    """With an ide, the entry must carry OBSERVAL_IDE so traces are attributed."""
    wrapped = _wrap_with_shim({"command": "npx", "args": []}, "fs", ide="cursor")
    assert wrapped["env"]["OBSERVAL_IDE"] == "cursor"


def test_wrap_with_shim_preserves_existing_env():
    wrapped = _wrap_with_shim({"command": "npx", "args": [], "env": {"FOO": "bar"}}, "fs", ide="cursor")
    assert wrapped["env"] == {"FOO": "bar", "OBSERVAL_IDE": "cursor"}


def test_wrap_with_shim_skips_remote_url():
    entry = {"url": "https://example.com/mcp"}
    assert _wrap_with_shim(entry, "remote", ide="cursor") == entry


def test_shim_config_file_injects_ide(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"fs": {"command": "npx", "args": ["-y", "pkg"]}}}))
    count = _shim_config_file(cfg, "cursor", dry_run=False)
    assert count == 1
    data = json.loads(cfg.read_text())
    entry = data["mcpServers"]["fs"]
    assert entry["command"] == "observal-shim"
    assert entry["env"]["OBSERVAL_IDE"] == "cursor"
    assert _is_already_shimmed(entry)


def test_shim_config_file_idempotent(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"fs": {"command": "npx", "args": ["-y", "pkg"]}}}))
    assert _shim_config_file(cfg, "cursor", dry_run=False) == 1
    # second run: already shimmed, no new changes
    assert _shim_config_file(cfg, "cursor", dry_run=False) == 0
