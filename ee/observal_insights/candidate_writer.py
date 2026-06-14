# SPDX-FileCopyrightText: 2026 Swathi Saravanan <ss4522@cornell.edu>
# SPDX-License-Identifier: LicenseRef-Observal-Enterprise

"""Module 1 — deterministic candidate generation from an insight report.

The self-learning loop's "propose" step. We do NOT let an LLM decide *whether*
a change should exist — that is determined by a deterministic classifier over the
report's already-grounded ``suggestions[].fix_type`` field. The LLM is used only
to *write the prose body* of a cursor rule, conditioned on the suggestion and a
few real session excerpts. This preserves the LLM-explains-doesn't-score
invariant: the verification spine (metrics, regression detector, report schema)
is untouched and the candidate's existence is purely deterministic.

Public:
    write_candidate(report_id) -> CandidateArtifact   (async; persists, status=pending)

Pure cores (unit-tested directly, no DB/LLM):
    classify_suggestion, select_target_suggestions, select_friction_sessions,
    suggestion_id, build_cursor_rule_mdc, extract_working_dirs
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

# ── Deterministic fix_type -> artifact_type classifier ──────────────────────
# fix_type values are produced by ee/observal_insights/sections.py (the report
# narrative). This mapping is the *only* thing that decides a candidate's type.

# Prompt-shaped fixes. On a Cursor agent these are materialized as .mdc rules
# (Cursor has no separate system prompt — prompts/skills are rules files), so
# they classify as cursor_rule instead of prompt_edit.
_PROMPT_FIX_TYPES = frozenset({"system_prompt_addition", "context_expansion", "workflow_change"})
_TOOL_FIX_TYPES = frozenset(
    {"tool_configuration", "mcp_addition", "mcp_removal", "skill_addition", "skill_removal"}
)
# fix_types we deliberately refuse to auto-apply (too broad / not a single edit).
_REJECT_FIX_TYPES = frozenset({"agent_upgrade"})

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class CandidateArtifact:
    """In-memory view returned by write_candidate (mirrors the ORM row)."""

    artifact_type: str
    content: str
    source_report_id: str
    source_suggestions: list[str] = field(default_factory=list)
    motivating_session_ids: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    id: str | None = None


def classify_suggestion(suggestion: dict, agent_ides: list[str]) -> str | None:
    """Map one suggestion to an artifact_type, or None to reject it.

    Deterministic — driven by ``fix_type`` and the agent's target IDEs. Never
    calls an LLM. Returns one of {cursor_rule, prompt_edit, tool_config_change}
    or None when the suggestion does not cleanly map.
    """
    fix_type = (suggestion.get("fix_type") or "").strip()
    if not fix_type or fix_type in _REJECT_FIX_TYPES:
        return None
    if fix_type in _TOOL_FIX_TYPES:
        return "tool_config_change"
    if fix_type in _PROMPT_FIX_TYPES:
        return "cursor_rule" if "cursor" in (agent_ides or []) else "prompt_edit"
    return None  # unknown fix_type — reject rather than guess


def suggestion_id(report_id: str, index: int, title: str) -> str:
    """Stable synthetic id for a suggestion (the report doesn't assign ids)."""
    h = hashlib.sha1(f"{report_id}|{index}|{title}".encode()).hexdigest()
    return f"sg_{h[:16]}"


def select_target_suggestions(
    suggestions: list[dict], agent_ides: list[str]
) -> tuple[str | None, list[dict]]:
    """Pick the dominant artifact_type and the suggestions that map to it.

    One candidate is produced per report cycle. We choose the artifact_type of
    the highest-priority cleanly-mappable suggestion (priority high>medium>low,
    then report order) and bundle every same-type suggestion into it. Returns
    (artifact_type, [suggestions]) or (None, []) if nothing maps.
    """
    mapped: list[tuple[int, dict, str]] = []
    for idx, sug in enumerate(suggestions):
        atype = classify_suggestion(sug, agent_ides)
        if atype is not None:
            mapped.append((idx, sug, atype))
    if not mapped:
        return None, []

    def _rank(item: tuple[int, dict, str]) -> tuple[int, int]:
        idx, sug, _ = item
        return (_PRIORITY_ORDER.get((sug.get("priority") or "low").lower(), 3), idx)

    mapped.sort(key=_rank)
    target_type = mapped[0][2]
    chosen = [sug for _, sug, atype in mapped if atype == target_type]
    return target_type, chosen


def _percentile_ranks(values: list[float]) -> list[float]:
    """Fractional rank in [0,1] for each value (ties share the lower rank)."""
    n = len(values)
    if n <= 1:
        return [1.0] * n
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    for pos, i in enumerate(order):
        ranks[i] = pos / (n - 1)
    return ranks


def select_friction_sessions(sessions: list[dict], k: int = 20) -> list[dict]:
    """Deterministically select the top-K friction sessions.

    Selection rule (documented in the candidate provenance): rank sessions by
    the sum of their duration percentile and tool-call-count percentile within
    the report period, descending; take the top K. error_rate/cost are excluded
    because they are structurally zero for transcript-ingested (Cursor) agents.
    """
    if not sessions:
        return []
    durs = [float(s.get("duration_seconds") or 0) for s in sessions]
    tools = [float(s.get("tool_call_count") or 0) for s in sessions]
    dpct = _percentile_ranks(durs)
    tpct = _percentile_ranks(tools)
    scored = [
        (dpct[i] + tpct[i], sessions[i]) for i in range(len(sessions))
    ]
    # Stable: break ties by session_id so the selection is reproducible.
    scored.sort(key=lambda x: (-x[0], str(x[1].get("session_id", ""))))
    return [s for _, s in scored[:k]]


_ABS_PATH_RE = re.compile(r"(/[\w.\-]+(?:/[\w.\-]+)+)")


def extract_working_dirs(excerpts: list[str]) -> list[str]:
    """Best-effort: derive working directories from session text.

    Pulls absolute paths out of transcript excerpts and reduces them to their
    containing directories. Used by gate-3 (scope) as the allowed write surface.
    Returns a sorted, de-duplicated list. May be empty (gate-3 then can't scope).
    """
    dirs: set[str] = set()
    for text in excerpts:
        for m in _ABS_PATH_RE.findall(text or ""):
            # Treat the path as a file if its last segment has an extension.
            last = m.rsplit("/", 1)[-1]
            d = m.rsplit("/", 1)[0] if "." in last else m
            if d and d != "/":
                dirs.add(d)
    return sorted(dirs)


def build_cursor_rule_mdc(description: str, glob: str, body: str, citations: list[dict]) -> str:
    """Assemble a .mdc cursor-rule file deterministically.

    Frontmatter + body + a citation block listing the session_ids and the
    suggestion text that motivated the rule (so every rule is traceable).
    """
    fm_desc = description.replace("\n", " ").strip()
    lines = [
        "---",
        f"description: {fm_desc}",
        f"globs: {glob}",
        "alwaysApply: false",
        "---",
        "",
        body.strip(),
        "",
        "<!-- observal:provenance",
        "This rule was generated by Observal's self-learning loop from an insight",
        "report. Existence determined deterministically by suggestion fix_type;",
        "body authored by the eval model. Motivating evidence:",
    ]
    for c in citations:
        sid = c.get("session_id", "")
        txt = (c.get("suggestion") or "").replace("\n", " ").strip()
        lines.append(f"- session {sid}: {txt}")
    lines.append("-->")
    return "\n".join(lines)


def _deterministic_body(suggestions: list[dict]) -> str:
    """Fallback body when the LLM is unavailable — pure, from the suggestions."""
    parts = []
    for s in suggestions:
        action = (s.get("action") or "").strip()
        if action:
            parts.append(f"- {action}")
    return "\n".join(parts) or "Follow the guidance below."


def _glob_for_dirs(working_dirs: list[str]) -> str:
    """Scope the rule to the motivating working dirs (gate-3 enforces this)."""
    if not working_dirs:
        return "**/*"
    if len(working_dirs) == 1:
        return f"{working_dirs[0]}/**"
    return "{" + ",".join(f"{d}/**" for d in working_dirs) + "}"


# ── Async orchestrator (DI-backed) ──────────────────────────────────────────


async def _llm_rule_body(suggestions: list[dict], excerpts: list[str]) -> str:
    """Ask the eval model to write the rule body. Falls back deterministically."""
    from ._deps import get_call_model

    try:
        call_model = get_call_model()
    except RuntimeError:
        return _deterministic_body(suggestions)

    sug_text = "\n".join(f"- {s.get('title','')}: {s.get('action','')}" for s in suggestions)
    ex_text = "\n\n".join(excerpts[:3])
    prompt = (
        "You are writing a concise Cursor rule body (markdown, no frontmatter) that "
        "encodes the following improvement(s) for an AI coding agent. Base it strictly "
        "on the suggestions and the real session excerpts; do not invent capabilities.\n\n"
        f"SUGGESTIONS:\n{sug_text}\n\nSESSION EXCERPTS:\n{ex_text}\n\n"
        'Return JSON: {"body": "<markdown rule body>"}'
    )
    try:
        result = await call_model(prompt)
        body = (result or {}).get("body", "").strip()
        return body or _deterministic_body(suggestions)
    except Exception:
        return _deterministic_body(suggestions)


async def write_candidate(report_id: str):
    """Build and persist one CandidateArtifact for the given report.

    Returns the persisted ORM CandidateArtifact (status=pending), or None when
    the report has no cleanly-mappable suggestions.
    """
    from sqlalchemy import select

    from models.agent import Agent
    from models.candidate_artifact import CandidateArtifact as ORMCandidate
    from models.insight_report import InsightReport

    from ._deps import get_db_session

    session_factory = get_db_session()
    async with session_factory() as db:
        report = (
            await db.execute(select(InsightReport).where(InsightReport.id == report_id))
        ).scalar_one_or_none()
        if report is None:
            return None
        narrative = report.narrative or {}
        suggestions = (narrative.get("suggestions") or {}).get("items") or []
        if not suggestions:
            return None

        agent = (
            await db.execute(select(Agent).where(Agent.id == report.agent_id))
        ).scalar_one_or_none()
        agent_ides = list(getattr(agent, "supported_ides", []) or []) if agent else []

        artifact_type, chosen = select_target_suggestions(suggestions, agent_ides)
        if not artifact_type:
            return None

        # Stable ids for the chosen suggestions (by their index in the report).
        idx_by_obj = {id(s): i for i, s in enumerate(suggestions)}
        sug_ids = [
            suggestion_id(str(report_id), idx_by_obj[id(s)], s.get("title", "")) for s in chosen
        ]

        # Friction sessions + excerpts (read-only accessors).
        friction = await _fetch_friction_sessions(str(report.agent_id), report)
        motivating_ids = [s["session_id"] for s in friction]
        excerpts = await _fetch_excerpts(motivating_ids)
        working_dirs = extract_working_dirs(excerpts)

        citations = [
            {"session_id": sid, "suggestion": s.get("action", "")}
            for sid in motivating_ids[:5]
            for s in chosen[:1]
        ]

        if artifact_type == "cursor_rule":
            glob = _glob_for_dirs(working_dirs)
            body = await _llm_rule_body(chosen, excerpts)
            description = chosen[0].get("title", "Observal auto rule")
            content = build_cursor_rule_mdc(description, glob, body, citations)
        else:
            # prompt_edit / tool_config_change — deterministic structured doc.
            content = json.dumps(
                {
                    "artifact_type": artifact_type,
                    "actions": [s.get("action", "") for s in chosen],
                    "rationale": [s.get("why", "") for s in chosen],
                    "citations": citations,
                },
                indent=2,
            )

        provenance = {
            "selection_rule": (
                "top-K=20 sessions by (duration_pct + tool_call_count_pct) within report period"
            ),
            "fix_types": [s.get("fix_type") for s in chosen],
            "artifact_type": artifact_type,
            "motivating_working_dirs": working_dirs,
            "globs": [glob] if artifact_type == "cursor_rule" else [],
            "agent_ides": agent_ides,
        }

        row = ORMCandidate(
            agent_id=report.agent_id,
            source_report_id=report.id,
            artifact_type=artifact_type,
            content=content,
            source_suggestions=sug_ids,
            motivating_session_ids=motivating_ids,
            provenance=provenance,
            status="pending",
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row


async def _fetch_friction_sessions(agent_id: str, report) -> list[dict]:
    """Read session_stats_agg for the agent within the report period (read-only)."""
    from ._deps import get_query

    q = get_query()
    start = report.period_start.strftime("%Y-%m-%d %H:%M:%S") if report.period_start else "1970-01-01 00:00:00"
    end = report.period_end.strftime("%Y-%m-%d %H:%M:%S") if report.period_end else "2999-01-01 00:00:00"
    sql = """
        SELECT session_id,
               dateDiff('second', first_event_time, last_event_time) AS duration_seconds,
               tool_call_count
        FROM session_stats_agg FINAL
        WHERE agent_id = {aid:String}
          AND last_event_time >= {t0:String}
          AND last_event_time <= {t1:String}
        FORMAT JSON
    """
    try:
        r = await q(sql, {"param_aid": agent_id, "param_t0": start, "param_t1": end})
        r.raise_for_status()
        rows = r.json().get("data", [])
    except Exception:
        return []
    sessions = [
        {
            "session_id": row.get("session_id", ""),
            "duration_seconds": int(row.get("duration_seconds") or 0),
            "tool_call_count": int(row.get("tool_call_count") or 0),
        }
        for row in rows
        if row.get("session_id")
    ]
    return select_friction_sessions(sessions, k=20)


async def _fetch_excerpts(session_ids: list[str], per_session_chars: int = 600) -> list[str]:
    """Pull a short raw_line excerpt per session (read-only)."""
    from ._deps import get_query

    if not session_ids:
        return []
    q = get_query()
    excerpts: list[str] = []
    for sid in session_ids[:3]:
        sql = """
            SELECT raw_line FROM session_events FINAL
            WHERE session_id = {sid:String}
            ORDER BY line_offset ASC LIMIT 4 FORMAT JSON
        """
        try:
            r = await q(sql, {"param_sid": sid})
            r.raise_for_status()
            rows = r.json().get("data", [])
            text = "\n".join(str(row.get("raw_line", "")) for row in rows)[:per_session_chars]
            if text:
                excerpts.append(text)
        except Exception:
            continue
    return excerpts
