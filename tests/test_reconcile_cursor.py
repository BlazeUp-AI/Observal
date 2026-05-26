# SPDX-FileCopyrightText: 2026 Yash Gadgil <yashgadgil08@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Cursor crash-recovery sweep in cmd_reconcile."""

import json
import os
import time

from observal_cli.cmd_reconcile import find_stale_sessions


def _create_cursor_session(tmp_path, session_id, content, age_secs=300):
    """Create a Cursor JSONL file at the expected path and backdate its mtime."""
    jsonl_dir = tmp_path / ".cursor" / "projects" / "test-project" / "agent-transcripts" / session_id
    jsonl_dir.mkdir(parents=True)
    jsonl_file = jsonl_dir / f"{session_id}.jsonl"
    jsonl_file.write_text(content)
    mtime = time.time() - age_secs
    os.utime(jsonl_file, (mtime, mtime))
    return jsonl_file


def _create_sync_state(tmp_path, session_id, offset=0, line_count=0, finalized=False):
    """Write a sync_state.json entry for the given session."""
    state_dir = tmp_path / ".observal"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "sync_state.json"
    entry = {"offset": offset, "line_count": line_count, "finalized": finalized}
    data = json.loads(state_file.read_text()) if state_file.exists() else {}
    data[session_id] = entry
    state_file.write_text(json.dumps(data))


class TestCursorStaleDetection:
    def test_stale_cursor_session_detected(self, tmp_path):
        session_id = "cursor-sess-001"
        content = '{"type": "user", "message": "hello"}\n'
        _create_cursor_session(tmp_path, session_id, content)
        _create_sync_state(tmp_path, session_id, offset=0, line_count=0)

        stale = find_stale_sessions(home=tmp_path)

        assert len(stale) == 1
        assert stale[0]["session_id"] == session_id
        assert stale[0]["file_size"] > 0
        assert stale[0]["cursor_offset"] == 0

    def test_finalized_cursor_session_skipped(self, tmp_path):
        session_id = "cursor-sess-002"
        content = '{"type": "user", "message": "hello"}\n'
        _create_cursor_session(tmp_path, session_id, content)
        _create_sync_state(tmp_path, session_id, offset=0, line_count=0, finalized=True)

        stale = find_stale_sessions(home=tmp_path)

        assert stale == []
