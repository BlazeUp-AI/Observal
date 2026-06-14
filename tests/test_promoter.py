# SPDX-License-Identifier: AGPL-3.0-only

"""Pure-core tests for Module 3 (promoter). The never-auto-merge invariant."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ee"))

from observal_insights.promoter import (
    _MAX_VERSION_LEN,
    _SAFE_VERSION_STATUSES,
    candidate_version_string,
    target_status,
)


def test_promote_maps_to_pending_review():
    assert target_status("promote") == ("promoted", "pending_review")


def test_inconclusive_maps_to_inconclusive_version():
    assert target_status("inconclusive") == ("verification_inconclusive", "verification_inconclusive")


def test_reject_writes_no_version():
    cand_status, version_status = target_status("reject")
    assert cand_status == "verification_failed"
    assert version_status is None


def test_unknown_recommendation_raises():
    with pytest.raises(ValueError):
        target_status("merge_to_active")


def test_version_string_does_not_compound():
    """Regression: basing on a prior candidate must not stack -candidate suffixes."""
    v1 = candidate_version_string("1.0.0", "7211abb4-aaaa")
    assert v1 == "1.0.0-candidate.7211abb4"
    # Feeding a prior candidate version back in strips the old suffix.
    v2 = candidate_version_string(v1, "bc12299b-bbbb")
    assert v2 == "1.0.0-candidate.bc12299b"
    assert v2.count("-candidate.") == 1


def test_version_string_bounded_to_column_width():
    long_base = "1.2.3-rc.4567890123456789012345678901234567890123456789"
    out = candidate_version_string(long_base, "deadbeef-cafe")
    assert len(out) <= _MAX_VERSION_LEN


def test_never_auto_merges_to_active_or_approved():
    """Invariant: no recommendation ever yields an active/approved version status."""
    for rec in ("promote", "inconclusive", "reject"):
        _, version_status = target_status(rec)
        assert version_status in (None, *_SAFE_VERSION_STATUSES)
        assert version_status not in ("approved", "active")
