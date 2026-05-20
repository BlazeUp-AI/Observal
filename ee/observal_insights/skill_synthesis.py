# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: LicenseRef-Observal-Enterprise
"""Skill synthesis — feeds insight report output back into the agent's rules.

The simplest possible self-learning loop:
    sessions → insight report (already runs) → extract actionable sections → inject into agent

No SQL pattern detection. No confidence formulas. No validation gate.
The insight report IS the analysis. We just pipe it back.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def _extract_suggestion_prompt_additions(narrative: dict) -> list[str]:
    """Extract system_prompt_addition suggestions from the narrative.

    V1 narrative has `suggestions` as a list of strings — no fix_type, so we
    can't filter. We skip these.

    V2 sections format has `suggestions` as a dict with `items[]` where each
    item has a `fix_type`. We only extract items where fix_type == "system_prompt_addition".

    Returns a list of action strings to inject directly into the agent's rules.
    """
    suggestions = narrative.get("suggestions")
    if not suggestions:
        return []

    # V2 structured format: {"intro": "...", "items": [...]}
    if isinstance(suggestions, dict):
        items = suggestions.get("items", [])
        additions = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("fix_type") == "system_prompt_addition":
                action = item.get("action", "").strip()
                if action:
                    additions.append(action)
        return additions

    # V1 format: list of strings — no fix_type metadata, skip
    return []


def synthesize_from_insight_report(report_content: dict) -> str | None:
    """Extract actionable guidance from an insight report and format as rules.

    Takes the report's narrative, facets summary, and regressions — the analysis
    that's already been done — and formats it into instructions the agent can follow.

    When the insight report contains structured suggestions with fix_type ==
    "system_prompt_addition", those are injected verbatim as high-priority
    behavioral directives.

    Args:
        report_content: The dict returned by generate_report_content().

    Returns:
        Formatted markdown string to inject into agent rules, or None if
        there's nothing actionable.
    """
    sections: list[str] = []

    narrative = report_content.get("narrative", {})
    facets_summary = report_content.get("facets_summary", {})
    regressions = report_content.get("regressions", [])

    # -- At a glance (already synthesized by the insight LLM) --
    at_a_glance = narrative.get("at_a_glance", {})
    # V1: at_a_glance is a string; V2: it's a dict with whats_working, whats_hindering, quick_win
    if isinstance(at_a_glance, str):
        whats_working = ""
        whats_hindering = ""
        quick_win = ""
    else:
        whats_working = at_a_glance.get("whats_working", "")
        whats_hindering = at_a_glance.get("whats_hindering", "")
        quick_win = at_a_glance.get("quick_win", "")

    # -- System prompt additions from structured suggestions (V2 only) --
    prompt_additions = _extract_suggestion_prompt_additions(narrative)

    # -- Repeated instructions (direct user corrections — the gold signal) --
    repeated_instructions = facets_summary.get("repeated_instructions", [])

    # -- Friction points --
    friction_points = facets_summary.get("friction_types", {})
    if isinstance(friction_points, list):
        friction_points = dict(friction_points)

    # -- Effective vs problematic tools --
    tools_effective = facets_summary.get("tools_effective", {})
    tools_problematic = facets_summary.get("tools_problematic", {})

    # aggregate_facets returns sorted list of tuples; handle both formats
    if isinstance(tools_effective, list):
        tools_effective = dict(tools_effective)
    if isinstance(tools_problematic, list):
        tools_problematic = dict(tools_problematic)

    # -- Inject system_prompt_additions first (highest priority) --
    if prompt_additions:
        lines = ["### Behavioral directives"]
        lines.append("")
        lines.append("*Auto-generated from insight analysis. Follow these strictly.*")
        lines.append("")
        for addition in prompt_additions:
            lines.append(f"- {addition}")
        sections.append("\n".join(lines))

    # Build the "what to keep doing" section
    keep_doing: list[str] = []
    if whats_working and whats_working.lower() not in ("n/a", "no clear value delivered in this period"):
        keep_doing.append(whats_working)
    if tools_effective:
        top_tools = sorted(tools_effective.items(), key=lambda x: x[1], reverse=True)[:3]
        for tool, count in top_tools:
            keep_doing.append(f"Use `{tool}` — effective across {count} sessions")

    # Build the "what to avoid" section
    avoid: list[str] = []
    if whats_hindering and whats_hindering.lower() != "n/a":
        avoid.append(whats_hindering)
    if repeated_instructions:
        # These are the highest-confidence signals — users literally telling the agent
        for instruction in repeated_instructions[:5]:
            if isinstance(instruction, str):
                avoid.append(f'Users repeatedly say: "{instruction}"')
            elif isinstance(instruction, dict):
                text = instruction.get("instruction", instruction.get("text", ""))
                count = instruction.get("count", 0)
                if text:
                    avoid.append(f'"{text}" ({count} sessions)' if count else f'"{text}"')
    if tools_problematic:
        top_problematic = sorted(tools_problematic.items(), key=lambda x: x[1], reverse=True)[:3]
        for tool, count in top_problematic:
            avoid.append(f"Avoid `{tool}` — caused friction in {count} sessions")
    if friction_points:
        top_friction = sorted(friction_points.items(), key=lambda x: x[1], reverse=True)[:3]
        for friction, count in top_friction:
            avoid.append(f"{friction} ({count} sessions)")

    # Build regressions section
    regression_lines: list[str] = []
    for reg in regressions[:3]:
        metric = reg.get("metric", "")
        direction = reg.get("direction", "")
        pct = reg.get("change_pct", 0)
        if metric and direction:
            regression_lines.append(f"{metric}: {direction} {abs(pct):.0f}%")

    # Assemble
    if keep_doing:
        sections.append("### What works\n" + "\n".join(f"- {line}" for line in keep_doing))

    if avoid:
        sections.append("### What to avoid\n" + "\n".join(f"- {line}" for line in avoid))

    if quick_win and quick_win.lower() != "n/a":
        sections.append(f"### Quick win\n- {quick_win}")

    if regression_lines:
        sections.append("### Recent regressions (be careful)\n" + "\n".join(f"- {line}" for line in regression_lines))

    if not sections:
        return None

    header = "## Learned from Production\n\n*Auto-updated from the latest insight report. Follow these guidelines.*\n"
    return header + "\n\n".join(sections)
