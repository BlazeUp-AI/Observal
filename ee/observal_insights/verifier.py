# SPDX-FileCopyrightText: 2026 Swathi Saravanan <ss4522@cornell.edu>
# SPDX-License-Identifier: LicenseRef-Observal-Enterprise

"""Module 2 — candidate verification (the core contribution).

Gates a candidate before it can be promoted. There is no agent-execution harness
on the platform, so true regression *replay* is impossible; gate-1 is therefore a
real, honest STUB that returns "inconclusive" and never fabricates metrics. The
remaining gates are static and falsifiable:

  gate-0 provenance  — hard fail on zero motivating sessions / zero globs
  gate-1 regression  — INCONCLUSIVE stub (replay needs an execution harness; TODO)
  gate-2 freeze-list — hard fail on any xfail signature with zero matching
                       tokens in the candidate body (static reframe of xfail)
  gate-3 scope       — hard fail on any glob outside the motivating sessions'
                       working directories (prevents one repo's rule bleeding
                       into another)

The eventual regression *watch* (next report period) reuses the unchanged
detect_regressions + its thresholds — that is longitudinal and lives outside
this verifier.

Public:
    verify_candidate(candidate_id) -> VerificationResult   (async; persists result)

Pure cores (unit-tested directly):
    gate_provenance, gate_regression_replay, gate_freeze_list, gate_scope,
    glob_bases, aggregate_result
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

HARD_GATES = ("provenance", "freeze_list", "scope")


@dataclass
class VerificationResult:
    passed: bool
    recommendation: str  # "promote" | "reject" | "inconclusive"
    per_gate: dict = field(default_factory=dict)
    diffs: list = field(default_factory=list)
    baseline_metrics: dict | None = None
    candidate_metrics: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ── Gate 0: provenance ──────────────────────────────────────────────────────


def gate_provenance(motivating_session_ids: list[str], globs: list[str], artifact_type: str) -> dict:
    """Hard fail on zero motivating sessions, or (for cursor rules) zero globs."""
    if not motivating_session_ids:
        return {"gate": "provenance", "passed": False, "reason": "zero motivating sessions"}
    if artifact_type == "cursor_rule" and not [g for g in globs if g]:
        return {"gate": "provenance", "passed": False, "reason": "cursor_rule with zero globs"}
    return {"gate": "provenance", "passed": True, "reason": ""}


# ── Gate 1: regression replay (inconclusive stub) ───────────────────────────


def gate_regression_replay(baseline_metrics: dict | None) -> dict:
    """Honest stub: cannot re-run sessions, so cannot produce candidate_metrics.

    Returns status="inconclusive" with passed=None. It NEVER fabricates metrics
    and NEVER auto-passes or auto-fails. baseline_metrics are surfaced (read from
    the source report) so a future execution harness can diff against them.
    """
    return {
        "gate": "regression",
        "passed": None,
        "status": "inconclusive",
        "reason": (
            "no agent-execution harness available; candidate cannot be re-run to "
            "produce candidate_metrics"
        ),
        "baseline_metrics_available": baseline_metrics is not None,
        # TODO(self-learning): wire a real replay harness, then reuse the
        # unchanged detect_regressions(candidate_metrics, baseline_metrics) and
        # hard-fail on any flag with direction=degraded and severity>=medium.
        "todo": "implement execution harness; reuse detect_regressions for scoring",
    }


# ── Gate 2: freeze-list (static xfail) ──────────────────────────────────────


def gate_freeze_list(candidate_body: str, xfail_signatures: list[dict]) -> dict:
    """Hard fail on any xfail signature with zero matching tokens in the body.

    Each signature is {"id": str, "tokens": [str], "note": str}. A signature is
    "unaddressed" when none of its tokens appear in the candidate body. With an
    empty freeze-list (the current state — no xfail markers are populated yet)
    this gate passes vacuously.
    """
    body = candidate_body or ""
    violations = []
    for sig in xfail_signatures or []:
        tokens = sig.get("tokens") or []
        if tokens and not any(tok in body for tok in tokens):
            violations.append(sig.get("id", "<unknown>"))
    passed = not violations
    return {
        "gate": "freeze_list",
        "passed": passed,
        "reason": "" if passed else f"unaddressed xfail signatures: {violations}",
        "violations": violations,
        "signatures_checked": len(xfail_signatures or []),
    }


# ── Gate 3: scope ───────────────────────────────────────────────────────────


def glob_bases(glob: str) -> list[str]:
    """Extract the base directory(ies) a glob is rooted at.

    Handles brace expansion ({/a/**,/b/**}) and trailing wildcards. A relative
    or fully-wildcard glob (e.g. "**/*") yields "" — i.e. unscoped.
    """
    if not glob:
        return [""]
    inner = glob.strip()
    if inner.startswith("{") and inner.endswith("}"):
        parts = inner[1:-1].split(",")
    else:
        parts = [inner]
    bases = []
    for p in parts:
        p = p.strip()
        # strip trailing glob segments
        for marker in ("/**", "/*"):
            if p.endswith(marker):
                p = p[: -len(marker)]
        if p in ("**", "*", "**/*"):
            p = ""
        bases.append(p)
    return bases


def gate_scope(globs: list[str], working_dirs: list[str]) -> dict:
    """Hard fail on any glob whose base is outside all motivating working dirs.

    If no working dirs are known we cannot scope, so we pass with a note rather
    than hard-fail on missing ground truth. An unscoped glob ("**/*") fails when
    working dirs ARE known (it would bleed beyond the motivating repos).
    """
    globs = [g for g in (globs or []) if g]
    if not globs:
        return {"gate": "scope", "passed": True, "reason": "no globs to scope", "out_of_scope": []}
    if not working_dirs:
        return {
            "gate": "scope",
            "passed": True,
            "reason": "no working dirs known; cannot scope",
            "out_of_scope": [],
            "unscoped": True,
        }
    out_of_scope = []
    for g in globs:
        for base in glob_bases(g):
            if not base or not any(base == d or base.startswith(d.rstrip("/") + "/") for d in working_dirs):
                out_of_scope.append(g)
                break
    passed = not out_of_scope
    return {
        "gate": "scope",
        "passed": passed,
        "reason": "" if passed else f"globs outside motivating working dirs: {out_of_scope}",
        "out_of_scope": out_of_scope,
    }


# ── Aggregation ─────────────────────────────────────────────────────────────


def aggregate_result(gates: dict, baseline_metrics: dict | None = None) -> VerificationResult:
    """Combine gate outcomes into a VerificationResult.

    passed = every HARD gate (provenance, freeze_list, scope) passed.
    recommendation:
        - "reject"       if any hard gate failed
        - "inconclusive" if all hard gates pass but regression replay is inconclusive
        - "promote"      if all hard gates pass and regression replay passed
    A candidate is NEVER auto-merged to active — promotion is human-gated.
    """
    hard_passed = all(bool(gates[g]["passed"]) for g in HARD_GATES if g in gates)
    if not hard_passed:
        rec = "reject"
    else:
        reg = gates.get("regression", {})
        rec = "promote" if reg.get("passed") is True else "inconclusive"
    return VerificationResult(
        passed=hard_passed,
        recommendation=rec,
        per_gate=gates,
        baseline_metrics=baseline_metrics,
        candidate_metrics=None,
    )


# ── Async orchestrator (DI-backed) ──────────────────────────────────────────


async def _load_xfail_signatures(agent_id: str) -> list[dict]:
    """Load per-agent xfail signatures for the freeze-list gate.

    No xfail-marker store exists yet, so this returns []. Gate-2 then passes
    vacuously. Populating xfail signatures (a future markers table) activates it.
    """
    # TODO(self-learning): read xfail signatures from a session-markers store
    # once it exists; until then the freeze-list gate is inactive by design.
    return []


async def verify_candidate(candidate_id: str) -> VerificationResult:
    """Run all gates for a candidate, persist the result, and return it."""
    from sqlalchemy import select

    from models.candidate_artifact import CandidateArtifact as ORMCandidate
    from models.insight_report import InsightReport

    from ._deps import get_db_session

    session_factory = get_db_session()
    async with session_factory() as db:
        cand = (
            await db.execute(select(ORMCandidate).where(ORMCandidate.id == candidate_id))
        ).scalar_one_or_none()
        if cand is None:
            raise ValueError(f"candidate {candidate_id} not found")

        provenance = cand.provenance or {}
        globs = provenance.get("globs") or []
        working_dirs = provenance.get("motivating_working_dirs") or []
        motivating = cand.motivating_session_ids or []

        baseline_metrics = None
        if cand.source_report_id is not None:
            report = (
                await db.execute(
                    select(InsightReport).where(InsightReport.id == cand.source_report_id)
                )
            ).scalar_one_or_none()
            if report is not None:
                baseline_metrics = report.metrics

        xfail_signatures = await _load_xfail_signatures(str(cand.agent_id))

        gates = {
            "provenance": gate_provenance(motivating, globs, cand.artifact_type),
            "regression": gate_regression_replay(baseline_metrics),
            "freeze_list": gate_freeze_list(cand.content, xfail_signatures),
            "scope": gate_scope(globs, working_dirs),
        }
        result = aggregate_result(gates, baseline_metrics=baseline_metrics)

        cand.verification_result = result.to_dict()
        await db.commit()
        return result
