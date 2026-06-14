# SPDX-License-Identifier: AGPL-3.0-only

"""Pure-core tests for Module 2 (verifier). Every gate path is falsifiable."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ee"))

from observal_insights.verifier import (
    aggregate_result,
    gate_freeze_list,
    gate_provenance,
    gate_regression_replay,
    gate_scope,
    glob_bases,
)


# ── gate-0 provenance ────────────────────────────────────────────────────────

def test_provenance_fails_zero_sessions():
    g = gate_provenance([], ["/r/**"], "cursor_rule")
    assert g["passed"] is False and "motivating" in g["reason"]


def test_provenance_fails_cursor_rule_zero_globs():
    g = gate_provenance(["s1"], [], "cursor_rule")
    assert g["passed"] is False and "glob" in g["reason"]


def test_provenance_passes_non_cursor_without_globs():
    assert gate_provenance(["s1"], [], "prompt_edit")["passed"] is True


# ── gate-1 regression (inconclusive stub) ────────────────────────────────────

def test_regression_is_always_inconclusive_never_passes():
    g = gate_regression_replay(baseline_metrics={"errors": {"error_rate": 0}})
    assert g["status"] == "inconclusive"
    assert g["passed"] is None  # never auto-pass/fail
    assert g["baseline_metrics_available"] is True


def test_regression_inconclusive_without_baseline():
    g = gate_regression_replay(baseline_metrics=None)
    assert g["passed"] is None and g["baseline_metrics_available"] is False


# ── gate-2 freeze-list ───────────────────────────────────────────────────────

def test_freeze_list_passes_vacuously_when_empty():
    assert gate_freeze_list("anything", [])["passed"] is True


def test_freeze_list_fails_on_unaddressed_signature():
    sigs = [{"id": "x1", "tokens": ["timeout", "ETIMEDOUT"]}]
    g = gate_freeze_list("rule body about file reads", sigs)
    assert g["passed"] is False and "x1" in g["violations"]


def test_freeze_list_passes_when_token_present():
    sigs = [{"id": "x1", "tokens": ["timeout"]}]
    assert gate_freeze_list("handle the timeout case", sigs)["passed"] is True


# ── glob_bases ───────────────────────────────────────────────────────────────

def test_glob_bases_strips_wildcards():
    assert glob_bases("/repo/**") == ["/repo"]
    assert glob_bases("/repo/src/*") == ["/repo/src"]


def test_glob_bases_brace_expansion():
    assert set(glob_bases("{/a/**,/b/**}")) == {"/a", "/b"}


def test_glob_bases_unscoped():
    assert glob_bases("**/*") == [""]


# ── gate-3 scope ─────────────────────────────────────────────────────────────

def test_scope_passes_in_scope():
    g = gate_scope(["/repo/**"], ["/repo"])
    assert g["passed"] is True


def test_scope_fails_out_of_scope():
    g = gate_scope(["/other/**"], ["/repo"])
    assert g["passed"] is False and "/other/**" in g["out_of_scope"]


def test_scope_fails_unscoped_glob_when_dirs_known():
    g = gate_scope(["**/*"], ["/repo"])
    assert g["passed"] is False


def test_scope_passes_when_no_working_dirs():
    g = gate_scope(["/anything/**"], [])
    assert g["passed"] is True and g.get("unscoped") is True


def test_scope_passes_when_no_globs():
    assert gate_scope([], ["/repo"])["passed"] is True


# ── aggregate_result ─────────────────────────────────────────────────────────

def _gates(prov=True, freeze=True, scope=True, reg_passed=None):
    return {
        "provenance": {"gate": "provenance", "passed": prov},
        "regression": {"gate": "regression", "passed": reg_passed, "status": "inconclusive"},
        "freeze_list": {"gate": "freeze_list", "passed": freeze},
        "scope": {"gate": "scope", "passed": scope},
    }


def test_aggregate_reject_on_hard_fail():
    r = aggregate_result(_gates(scope=False))
    assert r.passed is False and r.recommendation == "reject"


def test_aggregate_inconclusive_when_hard_pass_and_replay_inconclusive():
    r = aggregate_result(_gates())
    assert r.passed is True and r.recommendation == "inconclusive"


def test_aggregate_promote_only_when_replay_passes():
    r = aggregate_result(_gates(reg_passed=True))
    assert r.passed is True and r.recommendation == "promote"


def test_aggregate_candidate_metrics_never_fabricated():
    r = aggregate_result(_gates())
    assert r.candidate_metrics is None
