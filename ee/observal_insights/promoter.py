# SPDX-FileCopyrightText: 2026 Swathi Saravanan <ss4522@cornell.edu>
# SPDX-License-Identifier: LicenseRef-Observal-Enterprise

"""Module 3 — candidate promotion (human-gated).

Applies a VerificationResult to a candidate:

  - reject       -> candidate.status=verification_failed; NOT written to
                    agent_versions. Re-running next cron cycle is fine.
  - inconclusive -> a new agent_versions row with status=verification_inconclusive
                    (surfaced for human review, clearly marked not-fully-verified)
  - promote      -> a new agent_versions row with status=pending_review

A candidate is NEVER auto-merged to an active/approved version. The terminal
human-facing state is always pending_review or verification_inconclusive, and a
human must approve before it becomes active.

Public:
    promote_candidate(candidate_id, verification_result) -> dict   (async)

Pure core (unit-tested):
    target_status
"""

from __future__ import annotations

import re
import uuid

# Candidates always diff against the stable, human-approved baseline — never
# against a prior unreviewed candidate — so version strings and prompts cannot
# compound across cron cycles. This strips an existing candidate suffix.
_CANDIDATE_SUFFIX_RE = re.compile(r"-candidate\..*$")
_MAX_VERSION_LEN = 50  # agent_versions.version is VARCHAR(50)

# Statuses a promotion may set on the produced agent_versions row. Deliberately
# excludes approved/active — promotion never bypasses human review.
_SAFE_VERSION_STATUSES = frozenset({"pending_review", "verification_inconclusive"})


def candidate_version_string(base_version: str, version_id: str) -> str:
    """Build a bounded candidate version that never compounds across cycles.

    Strips any existing ``-candidate.*`` suffix from the base so repeated cycles
    don't stack suffixes, then appends a fresh short id. Capped at VARCHAR(50).
    """
    clean = _CANDIDATE_SUFFIX_RE.sub("", base_version or "0.0.0")
    short = str(version_id)[:8]
    return f"{clean}-candidate.{short}"[:_MAX_VERSION_LEN]


def target_status(recommendation: str) -> tuple[str, str | None]:
    """Map a verification recommendation to (candidate_status, version_status).

    version_status is None when no agent_versions row should be written.
    Invariant: version_status is never an active/approved state.
    """
    if recommendation == "promote":
        return "promoted", "pending_review"
    if recommendation == "inconclusive":
        return "verification_inconclusive", "verification_inconclusive"
    if recommendation == "reject":
        return "verification_failed", None
    raise ValueError(f"unknown recommendation: {recommendation!r}")


async def promote_candidate(candidate_id: str, verification_result) -> dict:
    """Apply the verification outcome. Returns a summary dict."""
    from sqlalchemy import select

    from models.agent import AgentStatus, AgentVersion
    from models.candidate_artifact import (
        SYSTEM_AUTO_CANDIDATE_USER_ID,
    )
    from models.candidate_artifact import (
        CandidateArtifact as ORMCandidate,
    )

    from ._deps import get_db_session

    # Accept either a VerificationResult or a plain dict.
    if hasattr(verification_result, "to_dict"):
        vr_dict = verification_result.to_dict()
        recommendation = verification_result.recommendation
    else:
        vr_dict = dict(verification_result or {})
        recommendation = vr_dict.get("recommendation", "reject")

    cand_status, version_status = target_status(recommendation)
    assert version_status is None or version_status in _SAFE_VERSION_STATUSES, (
        "promotion must never set an active/approved status"
    )

    session_factory = get_db_session()
    async with session_factory() as db:
        cand = (
            await db.execute(select(ORMCandidate).where(ORMCandidate.id == candidate_id))
        ).scalar_one_or_none()
        if cand is None:
            raise ValueError(f"candidate {candidate_id} not found")

        if version_status is None:
            # reject: record outcome, do not write a version.
            cand.status = cand_status
            cand.verification_result = vr_dict
            await db.commit()
            return {"candidate_id": str(candidate_id), "status": cand_status, "version_id": None}

        # Base the candidate on the latest APPROVED version (the stable,
        # human-blessed baseline). Falling back to the latest-any version would
        # compound changes across cycles (candidate-on-candidate). If no approved
        # version exists, fall back to latest-any but strip its candidate suffix.
        base = (
            await db.execute(
                select(AgentVersion)
                .where(
                    AgentVersion.agent_id == cand.agent_id,
                    AgentVersion.status == AgentStatus.approved,
                )
                .order_by(AgentVersion.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if base is None:
            base = (
                await db.execute(
                    select(AgentVersion)
                    .where(AgentVersion.agent_id == cand.agent_id)
                    .order_by(AgentVersion.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

        new_version_id = uuid.uuid4()
        # Clean base so versions/prompts never compound across cron cycles.
        version_str = candidate_version_string(base.version if base else "0.0.0", str(new_version_id))
        new_prompt = base.prompt if base else ""
        if base and base.status == AgentStatus.approved and cand.artifact_type in ("prompt_edit", "cursor_rule"):
            # Only append onto an approved baseline prompt (clean). If we fell
            # back to a non-approved base, leave its prompt as-is to avoid
            # double-applying the same auto block.
            new_prompt = (new_prompt + "\n\n" + cand.content).strip()

        version = AgentVersion(
            id=new_version_id,
            agent_id=cand.agent_id,
            version=version_str,
            description=f"Auto-candidate ({cand.artifact_type}) from insight report",
            prompt=new_prompt,
            model_name=base.model_name if base else "us.amazon.nova-lite-v1:0",
            model_config_json=(base.model_config_json if base else {}) or {},
            models_by_ide=(base.models_by_ide if base else {}) or {},
            external_mcps=(base.external_mcps if base else []) or [],
            supported_ides=(base.supported_ides if base else []) or [],
            required_ide_features=(base.required_ide_features if base else []) or [],
            inferred_supported_ides=(base.inferred_supported_ides if base else []) or [],
            ide_configs=(base.ide_configs if base else None),
            status=AgentStatus(version_status),
            is_prerelease=True,
            promoted_from=(base.id if base else None),
            released_by=uuid.UUID(SYSTEM_AUTO_CANDIDATE_USER_ID),
            source_report_id=cand.source_report_id,
            verification_result=vr_dict,
        )
        db.add(version)

        cand.status = cand_status
        cand.verification_result = vr_dict
        cand.promoted_version_id = new_version_id
        await db.commit()

        return {
            "candidate_id": str(candidate_id),
            "status": cand_status,
            "version_id": str(new_version_id),
            "version_status": version_status,
        }
