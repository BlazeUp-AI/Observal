# SPDX-FileCopyrightText: 2026 Aryan Iyappan <aryaniyappan2006@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for Cursor-specific doctor helpers.

All tests use tmp_path so they never touch the real ~/.cursor directory.

`typer` and `rich` are not installed in the minimal test environment, so we
inject lightweight stubs into sys.modules before importing cmd_doctor.  The
stubs only need to satisfy the module-level code that runs at import time;
the actual test targets (_check_cursor / _patch_cursor / _cleanup_cursor) use
nothing from those two packages.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import patch


# ── Minimal stubs for CLI-only deps ──────────────────────────


def _make_typer_stub() -> types.ModuleType:
    stub = types.ModuleType("typer")

    class _FakeApp:
        def callback(self, *a, **kw):
            def deco(f):
                return f

            return deco

        def command(self, *a, **kw):
            def deco(f):
                return f

            return deco

    stub.Typer = lambda **kw: _FakeApp()
    stub.Option = lambda *a, **kw: a[0] if a else None
    stub.Context = type("Context", (), {})
    stub.Exit = type("Exit", (SystemExit,), {})
    stub.confirm = lambda *a, **kw: False
    return stub


def _make_rich_stub() -> types.ModuleType:
    stub = types.ModuleType("rich")
    stub.print = print  # redirect to stdlib
    return stub


sys.modules.setdefault("typer", _make_typer_stub())
sys.modules.setdefault("rich", _make_rich_stub())

# Ensure `from rich import print as rprint` resolves from our stub
if hasattr(sys.modules["rich"], "print"):
    pass  # already set above


# ── Import helpers under test ────────────────────────────────

from observal_cli.cmd_doctor import _check_cursor, _cleanup_cursor, _patch_cursor  # noqa: E402


# ── Small test helpers ────────────────────────────────────────


def _write_hooks(cursor_dir: Path, hooks: dict) -> Path:
    hooks_path = cursor_dir / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(json.dumps({"version": 1, "hooks": hooks}))
    return hooks_path


def _observal_entry() -> dict:
    return {"command": f"{sys.executable} -m observal_cli.hooks.cursor_session_push", "type": "command"}


def _foreign_entry() -> dict:
    return {"command": "/usr/local/bin/my-custom-hook.sh", "type": "command"}


# ── _check_cursor ────────────────────────────────────────────


class TestCheckCursor:
    def test_no_cursor_dir_is_silent(self, tmp_path: Path):
        """`_check_cursor` silently skips when ~/.cursor does not exist."""
        issues: list[str] = []
        warnings: list[str] = []
        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            _check_cursor(issues, warnings)

        assert not issues
        assert not warnings

    def test_missing_hooks_json_adds_warning(self, tmp_path: Path):
        """`_check_cursor` warns when ~/.cursor exists but hooks.json is absent."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir(parents=True)

        issues: list[str] = []
        warnings: list[str] = []
        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            _check_cursor(issues, warnings)

        assert not issues
        assert len(warnings) == 1
        assert "hooks.json not found" in warnings[0]

    def test_hooks_present_no_warning(self, tmp_path: Path):
        """`_check_cursor` is silent when both hook events carry the session push."""
        cursor_dir = tmp_path / ".cursor"
        _write_hooks(
            cursor_dir,
            {
                "beforeSubmitPrompt": [_observal_entry()],
                "stop": [_observal_entry()],
            },
        )

        issues: list[str] = []
        warnings: list[str] = []
        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            _check_cursor(issues, warnings)

        assert not issues
        assert not warnings

    def test_missing_observal_hook_adds_warning(self, tmp_path: Path):
        """`_check_cursor` warns when hooks.json contains only foreign entries."""
        cursor_dir = tmp_path / ".cursor"
        _write_hooks(cursor_dir, {"beforeSubmitPrompt": [_foreign_entry()]})

        issues: list[str] = []
        warnings: list[str] = []
        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            _check_cursor(issues, warnings)

        assert not issues
        assert len(warnings) == 1
        assert "session push hooks not installed" in warnings[0]

    def test_invalid_json_adds_issue(self, tmp_path: Path):
        """`_check_cursor` raises an issue for a corrupted hooks.json."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir(parents=True)
        (cursor_dir / "hooks.json").write_text("not { valid json")

        issues: list[str] = []
        warnings: list[str] = []
        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            _check_cursor(issues, warnings)

        assert len(issues) == 1
        assert "not valid JSON" in issues[0]


# ── _patch_cursor ────────────────────────────────────────────


class TestPatchCursor:
    def test_no_cursor_dir_skips(self, tmp_path: Path):
        """`_patch_cursor` returns False when ~/.cursor does not exist."""
        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            result = _patch_cursor(dry_run=False)

        assert result is False

    def test_writes_hooks_when_absent(self, tmp_path: Path):
        """`_patch_cursor` creates hooks.json with both required events."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir(parents=True)
        hooks_path = cursor_dir / "hooks.json"

        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            result = _patch_cursor(dry_run=False)

        assert result is True
        assert hooks_path.exists()
        data = json.loads(hooks_path.read_text())
        assert "beforeSubmitPrompt" in data["hooks"]
        assert "stop" in data["hooks"]
        assert any("cursor_session_push" in e["command"] for e in data["hooks"]["beforeSubmitPrompt"])

    def test_dry_run_does_not_write(self, tmp_path: Path):
        """`_patch_cursor(dry_run=True)` returns True but never creates the file."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir(parents=True)
        hooks_path = cursor_dir / "hooks.json"

        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            result = _patch_cursor(dry_run=True)

        assert result is True
        assert not hooks_path.exists()

    def test_idempotent_patch(self, tmp_path: Path):
        """`_patch_cursor` is a no-op when Observal hooks are already present."""
        cursor_dir = tmp_path / ".cursor"
        _write_hooks(
            cursor_dir,
            {
                "beforeSubmitPrompt": [_observal_entry()],
                "stop": [_observal_entry()],
            },
        )

        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            result = _patch_cursor(dry_run=False)

        assert result is False

    def test_preserves_foreign_hooks(self, tmp_path: Path):
        """`_patch_cursor` keeps non-Observal hooks alongside the injected ones."""
        cursor_dir = tmp_path / ".cursor"
        _write_hooks(cursor_dir, {"beforeSubmitPrompt": [_foreign_entry()]})

        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            _patch_cursor(dry_run=False)

        data = json.loads((cursor_dir / "hooks.json").read_text())
        bp = data["hooks"]["beforeSubmitPrompt"]
        commands = [e["command"] for e in bp]
        assert any("cursor_session_push" in c for c in commands), "Observal hook not injected"
        assert any("my-custom-hook" in c for c in commands), "Foreign hook was removed"


# ── _cleanup_cursor ──────────────────────────────────────────


class TestCleanupCursor:
    def test_no_hooks_json_skips(self, tmp_path: Path):
        """`_cleanup_cursor` returns False when hooks.json is absent."""
        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            result = _cleanup_cursor(dry_run=False)

        assert result is False

    def test_removes_observal_hooks_keeps_foreign(self, tmp_path: Path):
        """`_cleanup_cursor` strips Observal entries while preserving foreign ones."""
        cursor_dir = tmp_path / ".cursor"
        _write_hooks(
            cursor_dir,
            {
                "beforeSubmitPrompt": [_observal_entry(), _foreign_entry()],
                "stop": [_observal_entry()],
            },
        )

        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            result = _cleanup_cursor(dry_run=False)

        assert result is True
        data = json.loads((cursor_dir / "hooks.json").read_text())
        hooks = data.get("hooks", {})
        # Foreign hook preserved in beforeSubmitPrompt
        bp = hooks.get("beforeSubmitPrompt", [])
        assert len(bp) == 1
        assert "my-custom-hook" in bp[0]["command"]
        # stop event fully removed (no entries left)
        assert "stop" not in hooks

    def test_dry_run_does_not_write(self, tmp_path: Path):
        """`_cleanup_cursor(dry_run=True)` reports changes but leaves the file unchanged."""
        cursor_dir = tmp_path / ".cursor"
        _write_hooks(cursor_dir, {"beforeSubmitPrompt": [_observal_entry()]})
        original_text = (cursor_dir / "hooks.json").read_text()

        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            result = _cleanup_cursor(dry_run=True)

        assert result is True
        assert (cursor_dir / "hooks.json").read_text() == original_text

    def test_nothing_to_clean_returns_false(self, tmp_path: Path):
        """`_cleanup_cursor` returns False when no Observal hooks are present."""
        cursor_dir = tmp_path / ".cursor"
        _write_hooks(cursor_dir, {"beforeSubmitPrompt": [_foreign_entry()]})

        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            result = _cleanup_cursor(dry_run=False)

        assert result is False

    def test_full_cleanup_removes_all_observal_entries(self, tmp_path: Path):
        """`_cleanup_cursor` clears every Observal hook across multiple events."""
        cursor_dir = tmp_path / ".cursor"
        _write_hooks(
            cursor_dir,
            {
                "beforeSubmitPrompt": [_observal_entry()],
                "stop": [_observal_entry()],
            },
        )

        with patch.object(Path, "home", staticmethod(lambda: tmp_path)):
            result = _cleanup_cursor(dry_run=False)

        assert result is True
        data = json.loads((cursor_dir / "hooks.json").read_text())
        hooks = data.get("hooks", {})
        assert "beforeSubmitPrompt" not in hooks
        assert "stop" not in hooks
