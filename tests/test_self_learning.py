# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for the self-learning suggestions pipeline.

Architecture: self-learning produces a new agent version (patch bump) with
suggestions baked into the prompt. That version enters the review queue.
Only after admin approval does it become the latest version served on install.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure project root is on path so ee/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ee.observal_insights.skill_synthesis import (
    _extract_suggestion_prompt_additions,
    synthesize_from_insight_report,
)
from services.agent_config_generator import _build_rules_content


# -- _extract_suggestion_prompt_additions tests --------------------------------


class TestExtractSuggestionPromptAdditions:
    def test_returns_empty_for_none_suggestions(self):
        assert _extract_suggestion_prompt_additions({}) == []

    def test_returns_empty_for_v1_string_list(self):
        """V1 narratives have suggestions as a list of strings — no fix_type."""
        narrative = {"suggestions": ["Use retry logic", "Optimize cache"]}
        assert _extract_suggestion_prompt_additions(narrative) == []

    def test_extracts_system_prompt_additions_from_v2(self):
        narrative = {
            "suggestions": {
                "intro": "Based on 50 sessions...",
                "items": [
                    {
                        "title": "Add file read check",
                        "action": "Always read a file before editing it.",
                        "why": "Reduces wrong_file friction by 60%",
                        "priority": "high",
                        "fix_type": "system_prompt_addition",
                        "expected_impact": "Reduce errors by 60%",
                        "confidence": "high",
                    },
                    {
                        "title": "Switch to pnpm",
                        "action": "Use pnpm instead of npm for package management.",
                        "why": "npm causes frequent failures",
                        "priority": "medium",
                        "fix_type": "tool_configuration",
                        "expected_impact": "Fewer tool failures",
                        "confidence": "medium",
                    },
                    {
                        "title": "Confirm before deleting",
                        "action": "Before deleting any file, confirm with the user.",
                        "why": "Users frequently reject file deletions",
                        "priority": "high",
                        "fix_type": "system_prompt_addition",
                        "expected_impact": "Reduce user rejections by 40%",
                        "confidence": "high",
                    },
                ],
            }
        }
        result = _extract_suggestion_prompt_additions(narrative)
        assert len(result) == 2
        assert "Always read a file before editing it." in result
        assert "Before deleting any file, confirm with the user." in result

    def test_skips_empty_actions(self):
        narrative = {
            "suggestions": {
                "intro": "...",
                "items": [
                    {
                        "title": "Empty",
                        "action": "   ",
                        "fix_type": "system_prompt_addition",
                    },
                ],
            }
        }
        assert _extract_suggestion_prompt_additions(narrative) == []

    def test_handles_non_dict_items_gracefully(self):
        narrative = {
            "suggestions": {
                "intro": "...",
                "items": ["not a dict", 42, None],
            }
        }
        assert _extract_suggestion_prompt_additions(narrative) == []


# -- synthesize_from_insight_report tests --------------------------------------


class TestSynthesizeFromInsightReport:
    def test_injects_system_prompt_additions_first(self):
        """system_prompt_addition suggestions should appear first in output."""
        report = {
            "narrative": {
                "at_a_glance": {"whats_working": "Fast navigation", "whats_hindering": "N/A", "quick_win": "N/A"},
                "suggestions": {
                    "intro": "Based on analysis...",
                    "items": [
                        {
                            "title": "Read before edit",
                            "action": "Always read file contents before editing.",
                            "fix_type": "system_prompt_addition",
                            "priority": "high",
                        },
                    ],
                },
            },
            "facets_summary": {"tools_effective": {"rg": 34}},
            "regressions": [],
            "sessions_analyzed": 50,
        }
        result = synthesize_from_insight_report(report)
        assert result is not None
        assert "### Behavioral directives" in result
        assert "Always read file contents before editing." in result
        # Directives should appear before "What works"
        directives_pos = result.index("### Behavioral directives")
        works_pos = result.index("### What works")
        assert directives_pos < works_pos

    def test_no_directives_section_without_system_prompt_additions(self):
        report = {
            "narrative": {
                "at_a_glance": {"whats_working": "Good stuff", "whats_hindering": "N/A", "quick_win": "N/A"},
                "suggestions": {
                    "intro": "...",
                    "items": [
                        {
                            "title": "Switch tool",
                            "action": "Use ripgrep instead of find",
                            "fix_type": "tool_configuration",
                            "priority": "medium",
                        },
                    ],
                },
            },
            "facets_summary": {},
            "regressions": [],
            "sessions_analyzed": 50,
        }
        result = synthesize_from_insight_report(report)
        assert result is not None
        assert "### Behavioral directives" not in result

    def test_extracts_whats_working(self):
        report = {
            "narrative": {
                "at_a_glance": {
                    "whats_working": "Fast file navigation using rg",
                    "whats_hindering": "N/A",
                    "quick_win": "N/A",
                }
            },
            "facets_summary": {"tools_effective": {"rg": 34, "git_diff": 12}},
            "regressions": [],
            "sessions_analyzed": 50,
        }
        result = synthesize_from_insight_report(report)
        assert result is not None
        assert "### What works" in result
        assert "rg" in result
        assert "34 sessions" in result

    def test_extracts_repeated_instructions(self):
        report = {
            "narrative": {
                "at_a_glance": {
                    "whats_working": "N/A",
                    "whats_hindering": "Agent uses npm",
                    "quick_win": "Switch to pnpm",
                }
            },
            "facets_summary": {"repeated_instructions": ["use pnpm not npm", "don't edit test files"]},
            "regressions": [],
            "sessions_analyzed": 50,
        }
        result = synthesize_from_insight_report(report)
        assert result is not None
        assert "### What to avoid" in result
        assert "use pnpm not npm" in result
        assert "don't edit test files" in result

    def test_returns_none_when_nothing_actionable(self):
        report = {
            "narrative": {"at_a_glance": {"whats_working": "N/A", "whats_hindering": "N/A", "quick_win": "N/A"}},
            "facets_summary": {},
            "regressions": [],
            "sessions_analyzed": 50,
        }
        result = synthesize_from_insight_report(report)
        assert result is None

    def test_returns_none_on_empty_report(self):
        result = synthesize_from_insight_report({})
        assert result is None

    def test_header_present(self):
        report = {
            "narrative": {"at_a_glance": {"whats_working": "Good stuff", "whats_hindering": "N/A", "quick_win": "N/A"}},
            "facets_summary": {},
            "regressions": [],
            "sessions_analyzed": 50,
        }
        result = synthesize_from_insight_report(report)
        assert result is not None
        assert "## Learned from Production" in result
        assert "Auto-updated from the latest insight report" in result

    def test_v1_string_at_a_glance(self):
        """V1 narrative has at_a_glance as a string."""
        report = {
            "narrative": {
                "at_a_glance": "Agent is healthy with 95% task completion",
                "suggestions": ["Improve cache utilization"],
            },
            "facets_summary": {"tools_effective": {"rg": 10}},
            "regressions": [],
            "sessions_analyzed": 30,
        }
        result = synthesize_from_insight_report(report)
        assert result is not None
        assert "rg" in result
        # V1 string suggestions should NOT produce directives
        assert "### Behavioral directives" not in result

    def test_regressions(self):
        report = {
            "narrative": {"at_a_glance": {"whats_working": "N/A", "whats_hindering": "N/A", "quick_win": "N/A"}},
            "facets_summary": {},
            "regressions": [{"metric": "tool_failure_rate", "direction": "increased", "change_pct": 15}],
            "sessions_analyzed": 50,
        }
        result = synthesize_from_insight_report(report)
        assert result is not None
        assert "### Recent regressions" in result
        assert "tool_failure_rate" in result
        assert "15%" in result


# -- _build_rules_content with insight_suggestions tests -----------------------


class TestBuildRulesContentWithSuggestions:
    """Test that the rules content builder can embed suggestions.

    In the version-proposal flow, suggestions are baked into the prompt of
    the new version. The _build_rules_content function's insight_suggestions
    param still works for pre-rendering, but the primary path is now via
    the version's prompt field.
    """

    def test_appends_suggestions_to_rules(self):
        agent = MagicMock()
        agent.prompt = "You are a helpful coding agent."
        agent.description = ""
        agent.components = []

        suggestions = "## Learned from Production\n\n### What works\n- Use rg"
        result = _build_rules_content(agent, insight_suggestions=suggestions)
        assert "## Learned from Production" in result
        assert "Use rg" in result
        assert "You are a helpful coding agent." in result

    def test_no_suggestions_when_none(self):
        agent = MagicMock()
        agent.prompt = "Base prompt."
        agent.description = ""
        agent.components = []

        result = _build_rules_content(agent, insight_suggestions=None)
        assert "Learned from Production" not in result
        assert result == "Base prompt."

    def test_suggestions_appear_after_prompt(self):
        agent = MagicMock()
        agent.prompt = "You are a coding assistant."
        agent.description = ""
        agent.components = []

        suggestions = "## Learned from Production\n\n### Behavioral directives\n- Always read before editing"
        result = _build_rules_content(agent, insight_suggestions=suggestions)
        prompt_pos = result.index("You are a coding assistant.")
        suggestions_pos = result.index("## Learned from Production")
        assert suggestions_pos > prompt_pos


# -- Version proposal logic tests ----------------------------------------------


class TestVersionProposalLogic:
    """Test the prompt composition logic used by the propose endpoint."""

    def test_new_prompt_appends_suggestions(self):
        """Simulate what the propose endpoint does: base prompt + suggestions."""
        base_prompt = "You are a coding agent. Follow best practices."
        suggestions_md = "## Learned from Production\n\n### What works\n- Use rg for search"

        new_prompt = f"{base_prompt}\n\n{suggestions_md}"
        assert "You are a coding agent." in new_prompt
        assert "## Learned from Production" in new_prompt
        assert new_prompt.index("coding agent") < new_prompt.index("Learned from Production")

    def test_idempotent_reproposal_strips_old_suggestions(self):
        """Re-proposing strips the old suggestions block before appending new ones."""
        marker = "## Learned from Production"
        old_prompt = "Base prompt.\n\n## Learned from Production\n\n### Old stuff\n- Outdated"
        new_suggestions = "## Learned from Production\n\n### What works\n- Use rg"

        if marker in old_prompt:
            base_prompt = old_prompt[: old_prompt.index(marker)].rstrip()
        else:
            base_prompt = old_prompt

        new_prompt = f"{base_prompt}\n\n{new_suggestions}"
        assert "Outdated" not in new_prompt
        assert "Use rg" in new_prompt
        assert new_prompt.startswith("Base prompt.")

    def test_version_bump(self):
        from services.versioning import bump_version

        assert bump_version("1.2.3", "patch") == "1.2.4"
        assert bump_version("0.1.0", "patch") == "0.1.1"


# -- Agent model toggle test ---------------------------------------------------


class TestSelfLearningToggle:
    def test_agent_model_default_disabled(self):
        from models.agent import Agent

        col = Agent.__table__.columns["self_learning_enabled"]
        assert col.default.arg is False
