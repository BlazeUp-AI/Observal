# SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com>
# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Agent Insights API endpoints."""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_role, resolve_prefix_id
from models.agent import Agent
from models.insight_meta_cache import InsightMetaCache
from models.insight_report import InsightReport, InsightReportStatus
from models.insight_session_facets import InsightSessionFacets
from models.user import User, UserRole
from schemas.insights import GenerateInsightRequest, InsightReportListItem, InsightReportResponse
from services.audit_helpers import audit
from services.insights import INSIGHTS_AVAILABLE, render_report_html
from services.redis import _get_arq_pool

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


def _require_insights():
    """Raise 402 if the insights package is not installed."""
    if not INSIGHTS_AVAILABLE:
        raise HTTPException(
            status_code=402,
            detail="Insights is an enterprise feature. Contact sales for access.",
        )


@router.post("/agents/{agent_id}/generate", response_model=InsightReportListItem)
async def generate_insight(
    agent_id: str,
    req: GenerateInsightRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Trigger generation of an insight report for an agent."""
    _require_insights()
    agent = await resolve_prefix_id(Agent, agent_id, db)

    if current_user.org_id is not None and agent.owner_org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Agent does not belong to your organization")

    period_days = req.period_days if req else 14
    now = datetime.now(UTC)
    period_start = now - timedelta(days=period_days)

    # Find previous completed report for regression linking
    prev_stmt = (
        select(InsightReport)
        .where(
            InsightReport.agent_id == agent.id,
            InsightReport.status == InsightReportStatus.completed,
        )
        .order_by(InsightReport.created_at.desc())
        .limit(1)
    )
    prev_result = await db.execute(prev_stmt)
    prev_report = prev_result.scalar_one_or_none()

    report = InsightReport(
        agent_id=agent.id,
        triggered_by=current_user.id,
        status=InsightReportStatus.pending,
        period_start=period_start,
        period_end=now,
        started_at=now,
        previous_report_id=prev_report.id if prev_report else None,
    )
    db.add(report)
    await db.flush()

    # Enqueue background job
    pool = await _get_arq_pool()
    await pool.enqueue_job("generate_insight_report", str(report.id))

    await audit(current_user, "insights.generate", resource_type="insight_report", resource_id=str(report.id))
    await db.commit()

    return InsightReportListItem.model_validate(report)


@router.get("/agents/{agent_id}/reports", response_model=list[InsightReportListItem])
async def list_reports(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """List insight reports for an agent, newest first."""
    _require_insights()
    agent = await resolve_prefix_id(Agent, agent_id, db)

    if current_user.org_id is not None and agent.owner_org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Agent does not belong to your organization")

    stmt = (
        select(InsightReport)
        .where(InsightReport.agent_id == agent.id)
        .order_by(InsightReport.created_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    reports = result.scalars().all()
    return [InsightReportListItem.model_validate(r) for r in reports]


@router.get("/reports/{report_id}", response_model=InsightReportResponse)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Get a single insight report by ID."""
    _require_insights()
    stmt = select(InsightReport).where(InsightReport.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Org-scope check via agent
    agent_stmt = select(Agent).where(Agent.id == report.agent_id)
    agent_result = await db.execute(agent_stmt)
    agent = agent_result.scalar_one_or_none()
    if agent and current_user.org_id is not None and agent.owner_org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Agent does not belong to your organization")

    resp = InsightReportResponse.model_validate(report)
    # Self-learning loop: surface candidate artifacts derived from this report
    # (read-only; frontend renders them, promotion stays human-gated).
    from models.candidate_artifact import CandidateArtifact

    cand_rows = (
        await db.execute(
            select(CandidateArtifact)
            .where(CandidateArtifact.source_report_id == report.id)
            .order_by(CandidateArtifact.created_at.desc())
        )
    ).scalars().all()
    resp.pending_candidates = [
        {
            "id": str(c.id),
            "artifact_type": c.artifact_type,
            "status": c.status,
            "source_suggestions": c.source_suggestions,
            "motivating_session_ids": c.motivating_session_ids,
            "promoted_version_id": str(c.promoted_version_id) if c.promoted_version_id else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cand_rows
    ]
    return resp


@router.post("/candidates/{candidate_id}/approve")
async def approve_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Human-gate a self-learning candidate: approve its agent version.

    The candidate's promoted version (status pending_review /
    verification_inconclusive) is set to approved — the only path by which an
    auto-generated change becomes active.
    """
    _require_insights()
    from models.agent import AgentStatus, AgentVersion
    from models.candidate_artifact import CandidateArtifact

    cand = (
        await db.execute(select(CandidateArtifact).where(CandidateArtifact.id == candidate_id))
    ).scalar_one_or_none()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not cand.promoted_version_id:
        raise HTTPException(status_code=400, detail="Candidate has no promoted version to approve")

    ver = (
        await db.execute(select(AgentVersion).where(AgentVersion.id == cand.promoted_version_id))
    ).scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail="Promoted version not found")

    ver.status = AgentStatus.approved
    ver.rejection_reason = None
    ver.reviewed_by = current_user.id
    ver.reviewed_at = datetime.now(UTC)
    cand.status = "approved"
    await db.commit()
    await audit(current_user, "insights.candidate.approve", resource_type="candidate_artifact", resource_id=str(cand.id))
    return {"candidate_id": str(cand.id), "version_id": str(ver.id), "status": "approved"}


@router.post("/candidates/{candidate_id}/reject")
async def reject_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Human-gate a self-learning candidate: reject its agent version."""
    _require_insights()
    from models.agent import AgentStatus, AgentVersion
    from models.candidate_artifact import CandidateArtifact

    cand = (
        await db.execute(select(CandidateArtifact).where(CandidateArtifact.id == candidate_id))
    ).scalar_one_or_none()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if cand.promoted_version_id:
        ver = (
            await db.execute(select(AgentVersion).where(AgentVersion.id == cand.promoted_version_id))
        ).scalar_one_or_none()
        if ver:
            ver.status = AgentStatus.rejected
            ver.rejection_reason = "Rejected from self-learning candidate review"
            ver.reviewed_by = current_user.id
            ver.reviewed_at = datetime.now(UTC)
    cand.status = "rejected"
    await db.commit()
    await audit(current_user, "insights.candidate.reject", resource_type="candidate_artifact", resource_id=str(cand.id))
    return {"candidate_id": str(cand.id), "status": "rejected"}


@router.get("/reports/{report_id}/export/html", response_class=HTMLResponse)
async def export_report_html(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Export an insight report as a self-contained HTML document."""
    _require_insights()
    stmt = select(InsightReport).where(InsightReport.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.status != InsightReportStatus.completed:
        raise HTTPException(status_code=400, detail="Report is not yet completed")

    # Org-scope check
    agent_stmt = select(Agent).where(Agent.id == report.agent_id)
    agent_result = await db.execute(agent_stmt)
    agent = agent_result.scalar_one_or_none()
    if agent and current_user.org_id is not None and agent.owner_org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Agent does not belong to your organization")

    # Build report dict for the renderer
    report_data = {
        "id": str(report.id),
        "agent_id": str(report.agent_id),
        "status": report.status.value if hasattr(report.status, "value") else str(report.status),
        "period_start": report.period_start,
        "period_end": report.period_end,
        "metrics": report.metrics,
        "narrative": report.narrative,
        "sessions_analyzed": report.sessions_analyzed,
    }

    html_content = render_report_html(report_data)

    return HTMLResponse(
        content=html_content,
        headers={
            "Content-Disposition": f'attachment; filename="insight-report-{report_id[:8]}.html"',
        },
    )


@router.delete("/agents/{agent_id}/reports")
async def clear_agent_reports(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Delete all insight reports and cached data for an agent."""
    _require_insights()
    agent = await resolve_prefix_id(Agent, agent_id, db)

    if current_user.org_id is not None and agent.owner_org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Agent does not belong to your organization")

    # Delete reports
    report_result = await db.execute(delete(InsightReport).where(InsightReport.agent_id == agent.id))

    # Delete cached session facets
    facets_result = await db.execute(delete(InsightSessionFacets).where(InsightSessionFacets.agent_id == agent.id))

    # Delete meta cache
    cache_result = await db.execute(delete(InsightMetaCache).where(InsightMetaCache.agent_id == agent.id))

    await audit(current_user, "insights.clear", resource_type="agent", resource_id=str(agent.id))
    await db.commit()

    return {
        "deleted_reports": report_result.rowcount,
        "deleted_facets": facets_result.rowcount,
        "deleted_cache": cache_result.rowcount,
    }


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Delete a single insight report."""
    _require_insights()
    stmt = select(InsightReport).where(InsightReport.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Org-scope check
    agent_stmt = select(Agent).where(Agent.id == report.agent_id)
    agent_result = await db.execute(agent_stmt)
    agent = agent_result.scalar_one_or_none()
    if agent and current_user.org_id is not None and agent.owner_org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Agent does not belong to your organization")

    await db.delete(report)
    await audit(current_user, "insights.delete_report", resource_type="insight_report", resource_id=str(report.id))
    await db.commit()

    return {"deleted": True, "report_id": report_id}
