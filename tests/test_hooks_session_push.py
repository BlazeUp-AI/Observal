# SPDX-FileCopyrightText: 2026 Avaya Aggarwal <aggarwal.avaya@yahoo.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for Claude Code session push helpers.

Covers: project_key_from_cwd, find_jsonl_file, read_cursor/write_cursor,
read_new_lines, build_payload, get_parent_session_id, load_config,
and read_agent_marker.

No network calls are made — all helpers under test are pure filesystem
operations or in-memory transformations.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from observal_cli.sessions.base import (
    build_payload,
    load_config,
    read_cursor,
    read_new_lines,
    write_cursor,
)
from observal_cli.sessions.claude_code import (
    find_jsonl_file,
    get_parent_session_id,
    project_key_from_cwd,
    read_agent_marker,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# project_key_from_cwd
# ---------------------------------------------------------------------------


class TestProjectKeyFromCwd:
    def test_simple_path(self):
        assert project_key_from_cwd("/home/user/myproject") == "-home-user-myproject"

    def test_root(self):
        assert project_key_from_cwd("/") == "-"

    def test_nested_path(self):
        result = project_key_from_cwd("/home/user/code/proj")
        assert result == "-home-user-code-proj"

    def test_no_leading_slash(self):
        # Relative paths: no leading slash so no leading dash
        assert project_key_from_cwd("relative/path") == "relative-path"

    def test_round_trips_deterministically(self):
        cwd = "/Users/dev/workspace/my-app"
        assert project_key_from_cwd(cwd) == project_key_from_cwd(cwd)


# ---------------------------------------------------------------------------
# find_jsonl_file
# ---------------------------------------------------------------------------


class TestFindJsonlFile:
    def test_primary_path_hit(self, tmp_path: Path):
        """Returns the primary path when the file exists at the expected location."""
        session_id = "abc123"
        project_key = "-home-user-proj"

        primary = tmp_path / ".claude" / "projects" / project_key / f"{session_id}.jsonl"
        primary.parent.mkdir(parents=True)
        primary.write_text("{}\n", encoding="utf-8")

        result = find_jsonl_file(session_id, project_key, home=tmp_path)
        assert result == primary

    def test_fallback_glob_hit(self, tmp_path: Path):
        """Falls back to glob scan when the primary path doesn't exist."""
        session_id = "deadbeef"
        project_key = "-home-user-proj"

        # File lives in a different project directory
        other_key = "-home-user-other"
        jsonl = tmp_path / ".claude" / "projects" / other_key / f"{session_id}.jsonl"
        jsonl.parent.mkdir(parents=True)
        jsonl.write_text("{}\n", encoding="utf-8")

        result = find_jsonl_file(session_id, project_key, home=tmp_path)
        assert result == jsonl

    def test_miss_returns_none(self, tmp_path: Path):
        """Returns None when the file doesn't exist anywhere."""
        result = find_jsonl_file("nosuchsession", "-home-user-proj", home=tmp_path)
        assert result is None

    def test_no_projects_dir_returns_none(self, tmp_path: Path):
        """Returns None gracefully when ~/.claude/projects doesn't exist."""
        result = find_jsonl_file("xyz", "-any-key", home=tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# read_cursor / write_cursor
# ---------------------------------------------------------------------------


class TestCursorRoundTrip:
    def test_missing_state_file_returns_zeros(self, tmp_path: Path):
        offset, line_count = read_cursor("session1", home=tmp_path)
        assert offset == 0
        assert line_count == 0

    def test_write_then_read(self, tmp_path: Path):
        write_cursor("sess-a", offset=512, line_count=10, home=tmp_path)
        offset, line_count = read_cursor("sess-a", home=tmp_path)
        assert offset == 512
        assert line_count == 10

    def test_multiple_sessions_isolated(self, tmp_path: Path):
        write_cursor("sess-x", offset=100, line_count=5, home=tmp_path)
        write_cursor("sess-y", offset=200, line_count=8, home=tmp_path)

        ox, lx = read_cursor("sess-x", home=tmp_path)
        oy, ly = read_cursor("sess-y", home=tmp_path)

        assert (ox, lx) == (100, 5)
        assert (oy, ly) == (200, 8)

    def test_finalized_flag_set(self, tmp_path: Path):
        write_cursor("sess-fin", offset=64, line_count=3, finalized=True, home=tmp_path)

        state_file = tmp_path / ".observal" / "sync_state.json"
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert data["sess-fin"]["finalized"] is True

    def test_finalized_flag_preserved_on_update(self, tmp_path: Path):
        """Once finalized=True, subsequent writes without the flag keep it."""
        write_cursor("sess-fp", offset=0, line_count=0, finalized=True, home=tmp_path)
        # Overwrite without finalized=True — should still be True
        write_cursor("sess-fp", offset=32, line_count=2, finalized=False, home=tmp_path)

        state_file = tmp_path / ".observal" / "sync_state.json"
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert data["sess-fp"]["finalized"] is True

    def test_corrupt_state_file_returns_zeros(self, tmp_path: Path):
        state_file = tmp_path / ".observal" / "sync_state.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("NOT JSON{{{{", encoding="utf-8")

        offset, line_count = read_cursor("any-session", home=tmp_path)
        assert offset == 0
        assert line_count == 0


# ---------------------------------------------------------------------------
# read_new_lines
# ---------------------------------------------------------------------------


class TestReadNewLines:
    def test_empty_file_returns_empty(self, tmp_path: Path):
        f = tmp_path / "session.jsonl"
        f.write_bytes(b"")
        lines, bytes_read = read_new_lines(f, offset=0)
        assert lines == []
        assert bytes_read == 0

    def test_offset_past_eof_returns_empty(self, tmp_path: Path):
        f = tmp_path / "session.jsonl"
        f.write_text('{"type": "text"}\n', encoding="utf-8")
        lines, bytes_read = read_new_lines(f, offset=9999)
        assert lines == []
        assert bytes_read == 0

    def test_reads_from_offset_zero(self, tmp_path: Path):
        content = '{"a": 1}\n{"b": 2}\n{"c": 3}\n'
        f = tmp_path / "session.jsonl"
        f.write_text(content, encoding="utf-8")
        lines, bytes_read = read_new_lines(f, offset=0)
        assert len(lines) == 3
        assert bytes_read == len(content.encode())

    def test_reads_from_mid_offset(self, tmp_path: Path):
        line1 = '{"a": 1}\n'
        line2 = '{"b": 2}\n'
        f = tmp_path / "session.jsonl"
        f.write_text(line1 + line2, encoding="utf-8")
        # Start reading after the first line
        lines, bytes_read = read_new_lines(f, offset=len(line1.encode()))
        assert len(lines) == 1
        assert lines[0].strip() == '{"b": 2}'

    def test_blank_lines_filtered(self, tmp_path: Path):
        f = tmp_path / "session.jsonl"
        f.write_text('{"x": 1}\n\n\n{"y": 2}\n', encoding="utf-8")
        lines, _ = read_new_lines(f, offset=0)
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# build_payload
# ---------------------------------------------------------------------------


class TestBuildPayload:
    def test_basic_schema_shape(self):
        payload = build_payload(
            session_id="sess1",
            lines=['{"type": "assistant"}'],
            start_offset=0,
            hook_event="UserPromptSubmit",
            line_count_before=0,
        )
        assert payload["session_id"] == "sess1"
        assert payload["ide"] == "claude-code"
        assert payload["hook_event"] == "UserPromptSubmit"
        assert payload["lines"] == ['{"type": "assistant"}']
        assert payload["start_offset"] == 0
        assert "final" not in payload

    def test_stop_event_adds_final_fields(self):
        payload = build_payload(
            session_id="sess2",
            lines=['{"type": "result"}'],
            start_offset=5,
            hook_event="Stop",
            line_count_before=5,
            new_offset=128,
        )
        assert payload["final"] is True
        assert payload["total_line_count"] == 6  # 5 before + 1 new
        assert payload["total_offset"] == 128

    def test_non_stop_event_no_final_fields(self):
        payload = build_payload(
            session_id="sess3",
            lines=["line1"],
            start_offset=0,
            hook_event="UserPromptSubmit",
            line_count_before=0,
        )
        assert "final" not in payload
        assert "total_line_count" not in payload
        assert "total_offset" not in payload

    def test_parent_session_id_forwarded(self):
        payload = build_payload(
            session_id="sub1",
            lines=["line"],
            start_offset=0,
            hook_event="UserPromptSubmit",
            line_count_before=0,
            parent_session_id="parent-sess",
        )
        assert payload["parent_session_id"] == "parent-sess"

    def test_no_cwd_skips_agent_marker(self):
        """Without a cwd, agent_id and agent_version should be None."""
        payload = build_payload(
            session_id="sess4",
            lines=["line"],
            start_offset=0,
            hook_event="UserPromptSubmit",
            line_count_before=0,
            cwd="",
        )
        assert payload["agent_id"] is None
        assert payload["agent_version"] is None


# ---------------------------------------------------------------------------
# get_parent_session_id
# ---------------------------------------------------------------------------


class TestGetParentSessionId:
    def test_subagent_path_returns_parent(self, tmp_path: Path):
        """Subagent files live at <project>/<parent_id>/subagents/<sub_id>.jsonl."""
        jsonl = tmp_path / "projects" / "proj" / "parent-sess-id" / "subagents" / "sub-123.jsonl"
        jsonl.parent.mkdir(parents=True)
        jsonl.touch()

        result = get_parent_session_id(jsonl)
        assert result == "parent-sess-id"

    def test_top_level_session_returns_none(self, tmp_path: Path):
        """Top-level session files are not inside a subagents/ directory."""
        jsonl = tmp_path / "projects" / "proj" / "top-level-sess.jsonl"
        jsonl.parent.mkdir(parents=True)
        jsonl.touch()

        result = get_parent_session_id(jsonl)
        assert result is None

    def test_short_path_returns_none(self, tmp_path: Path):
        """Paths with fewer parts than expected don't crash."""
        jsonl = Path("short.jsonl")
        result = get_parent_session_id(jsonl)
        assert result is None


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_missing_file_returns_none(self, tmp_path: Path):
        result = load_config(home=tmp_path)
        assert result is None

    def test_malformed_json_returns_none(self, tmp_path: Path):
        cfg = tmp_path / ".observal" / "config.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("{NOT VALID JSON", encoding="utf-8")
        assert load_config(home=tmp_path) is None

    def test_missing_server_url_returns_none(self, tmp_path: Path):
        _write_json(
            tmp_path / ".observal" / "config.json",
            {"access_token": "tok"},
        )
        assert load_config(home=tmp_path) is None

    def test_missing_token_returns_none(self, tmp_path: Path):
        _write_json(
            tmp_path / ".observal" / "config.json",
            {"server_url": "http://localhost:8000"},
        )
        assert load_config(home=tmp_path) is None

    def test_access_token_used_when_no_api_key(self, tmp_path: Path):
        _write_json(
            tmp_path / ".observal" / "config.json",
            {"server_url": "http://localhost:8000", "access_token": "short-token"},
        )
        cfg = load_config(home=tmp_path)
        assert cfg is not None
        assert cfg["access_token"] == "short-token"

    def test_api_key_takes_priority_over_access_token(self, tmp_path: Path):
        """api_key (30-day) should take precedence over access_token (1-hour)."""
        _write_json(
            tmp_path / ".observal" / "config.json",
            {
                "server_url": "http://localhost:8000",
                "access_token": "short-lived-token",
                "api_key": "long-lived-key",
            },
        )
        cfg = load_config(home=tmp_path)
        assert cfg is not None
        assert cfg["access_token"] == "long-lived-key"

    def test_valid_config_returns_all_fields(self, tmp_path: Path):
        _write_json(
            tmp_path / ".observal" / "config.json",
            {
                "server_url": "http://localhost:8000",
                "api_key": "mykey",
                "refresh_token": "reftoken",
            },
        )
        cfg = load_config(home=tmp_path)
        assert cfg is not None
        assert cfg["server_url"] == "http://localhost:8000"
        assert cfg["access_token"] == "mykey"
        assert cfg["refresh_token"] == "reftoken"
        assert "_config_path" in cfg


# ---------------------------------------------------------------------------
# read_agent_marker
# ---------------------------------------------------------------------------


class TestReadAgentMarker:
    def test_no_marker_file_returns_none_tuple(self, tmp_path: Path):
        result = read_agent_marker(str(tmp_path))
        assert result == (None, None)

    def test_marker_file_returns_agent_id(self, tmp_path: Path):
        marker = tmp_path / ".observal" / "agent"
        _write_json(marker, {"agent_id": "agent-xyz", "agent_version": "1.2.3"})

        agent_id, agent_version = read_agent_marker(str(tmp_path))
        assert agent_id == "agent-xyz"
        assert agent_version == "1.2.3"

    def test_first_push_before_pull_time_blocked(self, tmp_path: Path, monkeypatch):
        """Session created before pull should be blocked on first push (offset==0)."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Write a marker with a pulled_at time in the future
        pulled_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        marker = tmp_path / ".observal" / "agent"
        _write_json(marker, {"agent_id": "agent-abc", "pulled_at": pulled_at})

        # Create a session JSONL file (its ctime will be "now", before pulled_at)
        session_jsonl = tmp_path / "session.jsonl"
        session_jsonl.write_text('{"type":"text"}\n', encoding="utf-8")

        # Since offset==0 (first push) and session was created before pull, returns None
        result = read_agent_marker(str(tmp_path), session_jsonl=session_jsonl)
        assert result == (None, None)

    def test_resumed_session_ignores_pulled_at_guard(self, tmp_path: Path, monkeypatch):
        """Resumed sessions (offset > 0) bypass the pulled_at guard."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        pulled_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        marker = tmp_path / ".observal" / "agent"
        _write_json(marker, {"agent_id": "agent-resume", "pulled_at": pulled_at})

        session_jsonl = tmp_path / "rsession.jsonl"
        session_jsonl.write_text('{"type":"text"}\n', encoding="utf-8")

        # Simulate a resumed session by writing a non-zero cursor
        write_cursor("rsession", offset=42, line_count=3, home=tmp_path)

        agent_id, _ = read_agent_marker(str(tmp_path), session_jsonl=session_jsonl)
        assert agent_id == "agent-resume"

    def test_malformed_marker_file_returns_none(self, tmp_path: Path):
        marker = tmp_path / ".observal" / "agent"
        marker.parent.mkdir(parents=True)
        marker.write_text("{BAD JSON", encoding="utf-8")

        result = read_agent_marker(str(tmp_path))
        assert result == (None, None)
