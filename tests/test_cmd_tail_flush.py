# SPDX-FileCopyrightText: 2026 Riya Rani <rr1182764@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for observal_cli/cmd_tail_flush.py — tail_flush command module.

Covers:
- tail_flush with missing config (early return)
- tail_flush with missing session file (early return after sleep)
- tail_flush with no new lines (cursor finalised, no POST)
- tail_flush with successful POST (cursor finalised, subagent branching)
- tail_flush POST failure with retries (sleep cadence, log_error, no cursor write)
- tail_flush POST succeeds on second attempt (cursor finalised)
- main() entry point (argv handling, exception swallowing)
- Module constants (_FLUSH_DELAY_SECS, _MAX_RETRIES, _RETRY_DELAY_SECS)

All external I/O (filesystem, network, time.sleep) is mocked so the suite
runs fast with no real infrastructure.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Shared fixtures ──────────────────────────────────────────────────

_SESSION_ID = "test-session-abc123"
_JSONL_PATH = Path("/fake/home/.observal/sessions/test-session-abc123.jsonl")
_CONFIG = {"server_url": "http://localhost:8000", "access_token": "tok-xyz"}
_HOME = Path("/fake/home")


def _make_payload(**kwargs):
    base = {"session_id": _SESSION_ID, "lines": [], "hook_event": "Stop"}
    base.update(kwargs)
    return base


# ── Mock factories ───────────────────────────────────────────────────


def _make_sessions_base_mock(
    *,
    config=_CONFIG,
    cursor=(0, 0),
    new_lines=None,
    bytes_read=0,
    post_success=True,
):
    new_lines = new_lines if new_lines is not None else []
    m = MagicMock()
    m.load_config.return_value = config
    m.read_cursor.return_value = cursor
    m.read_new_lines.return_value = (new_lines, bytes_read)
    m.build_payload.return_value = _make_payload()
    m.post_to_server.return_value = post_success
    m.write_cursor.return_value = None
    m.log_error.return_value = None
    return m


def _make_reconcile_mock(*, jsonl_path=_JSONL_PATH):
    m = MagicMock()
    m._find_session_file.return_value = jsonl_path
    return m


def _make_claude_code_mock(*, parent_session_id=None):
    m = MagicMock()
    m.get_parent_session_id.return_value = parent_session_id
    m.push_subagent_sessions.return_value = None
    return m


# ── TestTailFlushNoConfig ────────────────────────────────────────────


class TestTailFlushNoConfig:
    def test_returns_without_sleeping_or_reading(self):
        """No config → returns immediately before sleep."""

        with (
            patch("observal_cli.cmd_tail_flush.time.sleep") as mock_sleep,
            patch("observal_cli.cmd_reconcile._find_session_file"),
        ):
            with patch.dict(
                "sys.modules",
                {
                    "observal_cli.sessions.base": _make_sessions_base_mock(config=None),
                    "observal_cli.cmd_reconcile": _make_reconcile_mock(),
                    "observal_cli.sessions.claude_code": _make_claude_code_mock(),
                },
            ):
                import importlib

                import observal_cli.cmd_tail_flush as mod

                importlib.reload(mod)
                mod.tail_flush(_SESSION_ID, home=_HOME)

            mock_sleep.assert_not_called()

    def test_tail_flush_uses_path_home_when_home_is_none(self):
        """Calling tail_flush without home= triggers the Path.home() default branch."""
        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": _make_sessions_base_mock(config=None),
                "observal_cli.cmd_reconcile": _make_reconcile_mock(),
                "observal_cli.sessions.claude_code": _make_claude_code_mock(),
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.Path") as mock_path:
                mock_path.home.return_value = _HOME
                mod.tail_flush(_SESSION_ID)  # no home= keyword — hits line 44
                mock_path.home.assert_called_once()


# ── TestTailFlushNoSessionFile ───────────────────────────────────────


class TestTailFlushNoSessionFile:
    def test_returns_when_jsonl_not_found(self):
        """_find_session_file returns None → returns after sleep, no reads."""

        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": _make_sessions_base_mock(config=_CONFIG),
                "observal_cli.cmd_reconcile": _make_reconcile_mock(jsonl_path=None),
                "observal_cli.sessions.claude_code": _make_claude_code_mock(),
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.time.sleep") as mock_sleep:
                mod.tail_flush(_SESSION_ID, home=_HOME)

            mock_sleep.assert_called_once_with(3)


# ── TestTailFlushNoNewLines ──────────────────────────────────────────


class TestTailFlushNoNewLines:
    def test_finalizes_cursor_when_nothing_new(self):
        """No new lines after Stop → write_cursor(finalized=True), return."""
        sessions_base = _make_sessions_base_mock(
            config=_CONFIG,
            cursor=(100, 5),
            new_lines=[],
            bytes_read=0,
        )

        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": sessions_base,
                "observal_cli.cmd_reconcile": _make_reconcile_mock(jsonl_path=_JSONL_PATH),
                "observal_cli.sessions.claude_code": _make_claude_code_mock(),
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.time.sleep"):
                mod.tail_flush(_SESSION_ID, home=_HOME)

        sessions_base.write_cursor.assert_called_once_with(_SESSION_ID, 100, 5, finalized=True, home=_HOME)
        sessions_base.post_to_server.assert_not_called()


# ── TestTailFlushSuccessfulPost ──────────────────────────────────────


class TestTailFlushSuccessfulPost:
    def test_posts_lines_writes_cursor_finalized(self):
        """New lines exist, POST succeeds → cursor written finalized."""
        new_lines = [b'{"type":"text"}\n', b'{"type":"usage"}\n']
        bytes_read = sum(len(line) for line in new_lines)
        sessions_base = _make_sessions_base_mock(
            config=_CONFIG,
            cursor=(50, 3),
            new_lines=new_lines,
            bytes_read=bytes_read,
            post_success=True,
        )
        claude_code = _make_claude_code_mock(parent_session_id=None)

        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": sessions_base,
                "observal_cli.cmd_reconcile": _make_reconcile_mock(jsonl_path=_JSONL_PATH),
                "observal_cli.sessions.claude_code": claude_code,
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.time.sleep"):
                mod.tail_flush(_SESSION_ID, home=_HOME)

        expected_new_offset = 50 + bytes_read
        sessions_base.write_cursor.assert_called_once_with(
            _SESSION_ID,
            expected_new_offset,
            3 + len(new_lines),
            finalized=True,
            home=_HOME,
        )

    def test_build_payload_called_with_correct_args(self):
        """build_payload receives the right session_id, lines, and hook_event."""
        new_lines = [b'{"a":1}\n']
        sessions_base = _make_sessions_base_mock(
            config=_CONFIG,
            cursor=(0, 0),
            new_lines=new_lines,
            bytes_read=8,
            post_success=True,
        )

        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": sessions_base,
                "observal_cli.cmd_reconcile": _make_reconcile_mock(jsonl_path=_JSONL_PATH),
                "observal_cli.sessions.claude_code": _make_claude_code_mock(),
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.time.sleep"):
                mod.tail_flush(_SESSION_ID, home=_HOME)

        sessions_base.build_payload.assert_called_once_with(
            session_id=_SESSION_ID,
            lines=new_lines,
            start_offset=0,
            hook_event="Stop",
            line_count_before=0,
            new_offset=8,
        )

    def test_push_subagent_sessions_called_for_parent(self):
        """When this IS the parent (get_parent_session_id → None), subagents are pushed."""
        new_lines = [b'{"x":1}\n']
        sessions_base = _make_sessions_base_mock(
            config=_CONFIG, cursor=(0, 0), new_lines=new_lines, bytes_read=8, post_success=True
        )
        claude_code = _make_claude_code_mock(parent_session_id=None)

        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": sessions_base,
                "observal_cli.cmd_reconcile": _make_reconcile_mock(jsonl_path=_JSONL_PATH),
                "observal_cli.sessions.claude_code": claude_code,
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.time.sleep"):
                mod.tail_flush(_SESSION_ID, home=_HOME)

        claude_code.push_subagent_sessions.assert_called_once_with(_SESSION_ID, _JSONL_PATH, _CONFIG, home=_HOME)

    def test_push_subagent_sessions_skipped_for_subagent(self):
        """When this is a subagent (get_parent_session_id → str), subagents are NOT pushed."""
        new_lines = [b'{"x":1}\n']
        sessions_base = _make_sessions_base_mock(
            config=_CONFIG, cursor=(0, 0), new_lines=new_lines, bytes_read=8, post_success=True
        )
        claude_code = _make_claude_code_mock(parent_session_id="parent-session-999")

        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": sessions_base,
                "observal_cli.cmd_reconcile": _make_reconcile_mock(jsonl_path=_JSONL_PATH),
                "observal_cli.sessions.claude_code": claude_code,
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.time.sleep"):
                mod.tail_flush(_SESSION_ID, home=_HOME)

        claude_code.push_subagent_sessions.assert_not_called()


# ── TestTailFlushPostFailure ─────────────────────────────────────────


class TestTailFlushPostFailure:
    def test_retries_on_post_failure(self):
        """POST failure triggers up to _MAX_RETRIES retries with sleep in between."""
        new_lines = [b'{"x":1}\n']
        sessions_base = _make_sessions_base_mock(
            config=_CONFIG, cursor=(0, 0), new_lines=new_lines, bytes_read=8, post_success=False
        )

        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": sessions_base,
                "observal_cli.cmd_reconcile": _make_reconcile_mock(jsonl_path=_JSONL_PATH),
                "observal_cli.sessions.claude_code": _make_claude_code_mock(),
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.time.sleep") as mock_sleep:
                mod.tail_flush(_SESSION_ID, home=_HOME)

        # Initial sleep + _MAX_RETRIES retry sleeps (default _MAX_RETRIES = 2)
        # Sleep called: once for flush delay, twice for retries
        assert mock_sleep.call_count == 1 + 2  # flush delay + 2 retry delays

    def test_logs_error_after_all_retries_exhausted(self):
        """After all retries fail, log_error is called."""
        new_lines = [b'{"x":1}\n']
        sessions_base = _make_sessions_base_mock(
            config=_CONFIG, cursor=(0, 0), new_lines=new_lines, bytes_read=8, post_success=False
        )

        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": sessions_base,
                "observal_cli.cmd_reconcile": _make_reconcile_mock(jsonl_path=_JSONL_PATH),
                "observal_cli.sessions.claude_code": _make_claude_code_mock(),
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.time.sleep"):
                mod.tail_flush(_SESSION_ID, home=_HOME)

        sessions_base.log_error.assert_called_once()
        error_msg = sessions_base.log_error.call_args[0][0]
        assert _SESSION_ID in error_msg
        assert "tail_flush" in error_msg

    def test_cursor_not_finalized_after_failed_retries(self):
        """On total failure, cursor is NOT written finalized (crash recovery handles it)."""
        new_lines = [b'{"x":1}\n']
        sessions_base = _make_sessions_base_mock(
            config=_CONFIG, cursor=(0, 0), new_lines=new_lines, bytes_read=8, post_success=False
        )

        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": sessions_base,
                "observal_cli.cmd_reconcile": _make_reconcile_mock(jsonl_path=_JSONL_PATH),
                "observal_cli.sessions.claude_code": _make_claude_code_mock(),
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.time.sleep"):
                mod.tail_flush(_SESSION_ID, home=_HOME)

        sessions_base.write_cursor.assert_not_called()

    def test_succeeds_on_second_attempt(self):
        """If POST fails once then succeeds, cursor IS written finalized."""
        new_lines = [b'{"x":1}\n']
        sessions_base = _make_sessions_base_mock(config=_CONFIG, cursor=(0, 0), new_lines=new_lines, bytes_read=8)
        # Fail first call, succeed second
        sessions_base.post_to_server.side_effect = [False, True]

        with patch.dict(
            "sys.modules",
            {
                "observal_cli.sessions.base": sessions_base,
                "observal_cli.cmd_reconcile": _make_reconcile_mock(jsonl_path=_JSONL_PATH),
                "observal_cli.sessions.claude_code": _make_claude_code_mock(),
            },
        ):
            import importlib

            import observal_cli.cmd_tail_flush as mod

            importlib.reload(mod)

            with patch("observal_cli.cmd_tail_flush.time.sleep"):
                mod.tail_flush(_SESSION_ID, home=_HOME)

        sessions_base.write_cursor.assert_called_once()
        _, kwargs = sessions_base.write_cursor.call_args
        assert kwargs.get("finalized") is True


# ── TestModuleConstants ──────────────────────────────────────────────


class TestModuleConstants:
    def test_flush_delay_is_positive(self):
        from observal_cli.cmd_tail_flush import _FLUSH_DELAY_SECS

        assert _FLUSH_DELAY_SECS > 0

    def test_max_retries_is_non_negative(self):
        from observal_cli.cmd_tail_flush import _MAX_RETRIES

        assert _MAX_RETRIES >= 0

    def test_retry_delay_is_positive(self):
        from observal_cli.cmd_tail_flush import _RETRY_DELAY_SECS

        assert _RETRY_DELAY_SECS > 0


# ── TestMain ─────────────────────────────────────────────────────────


class TestMain:
    def test_main_no_args_returns_silently(self):
        """main() with no argv → returns without error."""
        import observal_cli.cmd_tail_flush as mod

        with patch.object(sys, "argv", ["cmd_tail_flush"]):
            mod.main()  # should not raise

    def test_main_empty_session_id_returns_silently(self):
        """main() with empty string session_id → returns without error."""
        import observal_cli.cmd_tail_flush as mod

        with patch.object(sys, "argv", ["cmd_tail_flush", ""]):
            mod.main()  # should not raise

    def test_main_calls_tail_flush_with_session_id(self):
        """main() passes argv[1] to tail_flush."""
        import observal_cli.cmd_tail_flush as mod

        with (
            patch.object(sys, "argv", ["cmd_tail_flush", _SESSION_ID]),
            patch.object(mod, "tail_flush") as mock_tf,
        ):
            mod.main()

        mock_tf.assert_called_once_with(_SESSION_ID)

    def test_main_swallows_all_exceptions(self):
        """main() never propagates exceptions — background process safety."""
        import observal_cli.cmd_tail_flush as mod

        with (
            patch.object(sys, "argv", ["cmd_tail_flush", _SESSION_ID]),
            patch.object(mod, "tail_flush", side_effect=RuntimeError("boom")),
        ):
            mod.main()  # must not raise

    def test_main_swallows_keyboard_interrupt(self):
        """main() swallows even KeyboardInterrupt."""
        import observal_cli.cmd_tail_flush as mod

        def _raise_ki(*a, **kw):
            raise KeyboardInterrupt

        with (
            patch.object(sys, "argv", ["cmd_tail_flush", _SESSION_ID]),
            patch.object(mod, "tail_flush", side_effect=_raise_ki),
        ):
            mod.main()  # must not raise

    def test_main_except_block_is_reached(self):
        """Exercises the bare `except BaseException: pass` on line 122."""
        import observal_cli.cmd_tail_flush as mod

        with (
            patch.object(sys, "argv", ["cmd_tail_flush", _SESSION_ID]),
            patch.object(mod, "tail_flush", side_effect=SystemExit(1)),
        ):
            mod.main()  # SystemExit is a BaseException; must not propagate
