# SPDX-License-Identifier: AGPL-3.0-only

"""Pure-core tests for Module 1 (candidate_writer).

Falsifiable: each asserts a concrete classifier/selection/format outcome.
The async write_candidate orchestrator needs DB+LLM DI; see TODO at bottom.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ee"))

from observal_insights.candidate_writer import (
    build_cursor_rule_mdc,
    classify_suggestion,
    extract_working_dirs,
    select_friction_sessions,
    select_target_suggestions,
    suggestion_id,
)


# ── classify_suggestion ──────────────────────────────────────────────────────

def test_prompt_fix_on_cursor_agent_is_cursor_rule():
    s = {"fix_type": "system_prompt_addition"}
    assert classify_suggestion(s, ["cursor"]) == "cursor_rule"


def test_prompt_fix_on_non_cursor_agent_is_prompt_edit():
    s = {"fix_type": "context_expansion"}
    assert classify_suggestion(s, ["claude-code"]) == "prompt_edit"


def test_tool_fix_is_tool_config_change():
    for ft in ("tool_configuration", "mcp_addition", "skill_removal"):
        assert classify_suggestion({"fix_type": ft}, ["cursor"]) == "tool_config_change"


def test_agent_upgrade_is_rejected():
    assert classify_suggestion({"fix_type": "agent_upgrade"}, ["cursor"]) is None


def test_unknown_or_missing_fix_type_rejected():
    assert classify_suggestion({"fix_type": "nonsense"}, ["cursor"]) is None
    assert classify_suggestion({}, ["cursor"]) is None


# ── select_target_suggestions ────────────────────────────────────────────────

def test_select_dominant_type_by_priority():
    suggestions = [
        {"fix_type": "tool_configuration", "priority": "low", "title": "t"},
        {"fix_type": "system_prompt_addition", "priority": "high", "title": "p1"},
        {"fix_type": "context_expansion", "priority": "medium", "title": "p2"},
    ]
    atype, chosen = select_target_suggestions(suggestions, ["cursor"])
    assert atype == "cursor_rule"  # highest-priority mappable is the prompt fix
    assert {c["title"] for c in chosen} == {"p1", "p2"}  # both cursor_rule-type bundled


def test_select_returns_none_when_nothing_maps():
    atype, chosen = select_target_suggestions([{"fix_type": "agent_upgrade", "title": "x"}], ["cursor"])
    assert atype is None and chosen == []


# ── suggestion_id ────────────────────────────────────────────────────────────

def test_suggestion_id_stable_and_distinct():
    a = suggestion_id("r1", 0, "Add rule")
    assert a == suggestion_id("r1", 0, "Add rule")  # deterministic
    assert a != suggestion_id("r1", 1, "Add rule")  # index matters
    assert a.startswith("sg_")


# ── select_friction_sessions ─────────────────────────────────────────────────

def test_friction_selection_ranks_by_duration_and_tools():
    sessions = [
        {"session_id": "low", "duration_seconds": 10, "tool_call_count": 1},
        {"session_id": "mid", "duration_seconds": 100, "tool_call_count": 5},
        {"session_id": "high", "duration_seconds": 1000, "tool_call_count": 50},
    ]
    top = select_friction_sessions(sessions, k=2)
    assert [s["session_id"] for s in top] == ["high", "mid"]


def test_friction_selection_empty():
    assert select_friction_sessions([], k=20) == []


def test_friction_selection_caps_at_k():
    sessions = [{"session_id": str(i), "duration_seconds": i, "tool_call_count": i} for i in range(30)]
    assert len(select_friction_sessions(sessions, k=20)) == 20


# ── build_cursor_rule_mdc ────────────────────────────────────────────────────

def test_mdc_has_frontmatter_glob_body_and_citations():
    mdc = build_cursor_rule_mdc(
        description="Use filesystem MCP for file ops",
        glob="/repo/**",
        body="Always prefer the filesystem MCP.",
        citations=[{"session_id": "s1", "suggestion": "use fs mcp"}],
    )
    assert mdc.startswith("---")
    assert "globs: /repo/**" in mdc
    assert "description: Use filesystem MCP for file ops" in mdc
    assert "Always prefer the filesystem MCP." in mdc
    assert "session s1: use fs mcp" in mdc
    assert "observal:provenance" in mdc


# ── extract_working_dirs ─────────────────────────────────────────────────────

def test_extract_working_dirs_from_paths():
    excerpts = ["opened /Users/me/proj/src/app.py and /Users/me/proj/README.md"]
    dirs = extract_working_dirs(excerpts)
    assert "/Users/me/proj/src" in dirs
    assert "/Users/me/proj" in dirs


def test_extract_working_dirs_none():
    assert extract_working_dirs(["no paths here"]) == []


# TODO(self-learning): integration test for write_candidate() requires the
# insights DI (get_db_session/get_query/get_call_model) configured against a
# test DB + fake model. Pure cores above cover the deterministic logic; the
# orchestrator is exercised end-to-end via the worker pipeline in staging.
