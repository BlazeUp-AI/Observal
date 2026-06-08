# SPDX-FileCopyrightText: 2026 Aryan Iyappan <aryaniyappan2006@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
# ruff: noqa: E402, I001

"""Unit tests for Cursor-specific doctor helpers.

All tests use tmp_path so they never touch the real ~/.cursor directory.

When ``typer`` or ``rich`` are absent from the test environment (e.g. the
minimal CI matrix) we inject self-referential stubs into sys.modules *before*
importing cmd_doctor.  ``setdefault`` is a no-op when the real packages are
already present, so the stubs never interfere with other test files that
import typer directly.  The ``_Fake`` sentinel handles every attribute /
call pattern that typer and rich use at module-import time.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import patch


# ── Self-referential stub that satisfies any typer/rich usage ─


class _Fake:
    """A callable sentinel that returns itself for any attribute or call.

    Covers:
    - ``typer.Typer()``              → _Fake instance with .callback / .command
    - ``@app.callback(...)``         → decorator that returns the wrapped fn
    - ``@app.command(name=...)``     → decorator that returns the wrapped fn
    - ``typer.Option(default, ...)`` → returns the default value
    - ``typer.Argument(default,..)`` → returns the default value
    - ``typer.Context``              → usable as a type annotation
    - any other attribute access     → returns a new _Fake
    """

    def __init__(self, _default=None):
        self._default = _default

    def __call__(self, *args, **kwargs):
        # Decorator pattern: single callable arg → return it unchanged.
        if len(args) == 1 and callable(args[0]) and not isinstance(args[0], type):
            return args[0]
        # Option/Argument pattern: first positional arg is the default.
        if args:
            return args[0]
        return _Fake()

    def __getattr__(self, name: str) -> _Fake:
        return _Fake()


def _make_typer_stub() -> types.ModuleType:
    stub = types.ModuleType("typer")
    stub.__getattr__ = lambda name: _Fake()  # type: ignore[attr-defined]
    # Exit must be an exception subclass so `raise typer.Exit(...)` works.
    stub.Exit = type("Exit", (SystemExit,), {})  # type: ignore[attr-defined]
    return stub


def _make_rich_stub() -> types.ModuleType:
    stub = types.ModuleType("rich")
    stub.print = print  # type: ignore[attr-defined]
    return stub


# Only inject when the real packages are absent — setdefault is a no-op
# if typer/rich are already installed in the current Python environment.
sys.modules.setdefault("typer", _make_typer_stub())
sys.modules.setdefault("rich", _make_rich_stub())


# ── Import helpers under test (after stubs are in place) ─────

from observal_cli.cmd_doctor import _check_cursor, _cleanup_cursor, _patch_cursor


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
