# SPDX-FileCopyrightText: 2026 Observal contributors
# SPDX-License-Identifier: AGPL-3.0-only

import json

import pytest

from services.session_parsers import parse_raw_events
from services.session_parsers.base import basic_event, pick_timestamp
from services.session_parsers.ingest_classify import classify, extract_preview, extract_tool_info


def test_pick_timestamp_prefers_jsonl_timestamp_and_ignores_epoch_sentinel():
    assert (
        pick_timestamp(
            "2026-01-02T03:04:05.000Z",
            "2025-01-01 00:00:00.000",
            "2024-01-01 00:00:00.000",
        )
        == "2026-01-02 03:04:05.000"
    )
    assert (
        pick_timestamp(None, "1970-01-01 00:00:00.000", "2024-01-01 00:00:00.000")
        == "2024-01-01 00:00:00.000"
    )


def test_basic_event_includes_safe_defaults_and_optional_credits():
    event = basic_event(
        {
            "timestamp": "2026-01-01 00:00:00.000",
            "event_type": "kiro_credits",
            "content_preview": "1.2500 credits",
            "tool_name": None,
            "tool_id": "tool-1",
            "uuid": None,
            "parent_uuid": "parent-1",
            "content_length": 42,
            "credits": 1.25,
            "ide": "kiro",
        }
    )

    assert event["event_name"] == "kiro_credits"
    assert event["service_name"] == "kiro"
    assert event["attributes"]["tool_name"] == ""
    assert event["attributes"]["tool_id"] == "tool-1"
    assert event["attributes"]["credits"] == "1.25"


def test_parse_raw_events_dispatches_claude_code_user_prompt():
    raw_line = {
        "type": "user",
        "timestamp": "2026-01-02T03:04:05.000Z",
        "message": {"content": "please inspect the trace"},
    }

    events = parse_raw_events(
        [
            {
                "ide": "claude-code",
                "raw_line": json.dumps(raw_line),
                "timestamp": "1970-01-01 00:00:00.000",
                "ingested_at": "2026-01-02 03:04:06.000",
            }
        ]
    )

    assert events == [
        {
            "timestamp": "2026-01-02 03:04:05.000",
            "event_name": "hook_userpromptsubmit",
            "body": "please inspect the trace",
            "attributes": {"tool_input": "please inspect the trace"},
            "service_name": "claude-code",
        }
    ]


def test_parse_raw_events_falls_back_to_basic_event_for_bad_json():
    events = parse_raw_events(
        [
            {
                "ide": "claude-code",
                "raw_line": "{broken",
                "timestamp": "2026-01-02 03:04:05.000",
                "content_preview": "fallback preview",
                "event_type": "system",
            }
        ]
    )

    assert events[0]["event_name"] == "system"
    assert events[0]["body"] == "fallback preview"


def test_ingest_classifier_extracts_claude_tool_info_and_preview():
    parsed = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "Read", "input": {"file": "a.py"}}
            ]
        },
    }

    assert classify("claude-code", parsed) == "tool_call"
    assert extract_preview("claude-code", parsed, "tool_call") == "[tool_use: Read]"
    assert extract_tool_info("claude-code", parsed) == ("Read", "toolu_1")


def test_ingest_classifier_rejects_unknown_ide():
    with pytest.raises(KeyError):
        classify("unknown-ide", {"type": "user"})

