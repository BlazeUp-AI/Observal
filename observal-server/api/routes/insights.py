"""Agent Insights API endpoints."""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_role, resolve_prefix_id
from models.agent import Agent
from models.insight_report import InsightReport, InsightReportStatus
from models.user import User, UserRole
from schemas.insights import GenerateInsightRequest, InsightReportListItem, InsightReportResponse
from services.audit_helpers import audit
from services.redis import _get_arq_pool

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


@router.post("/agents/{agent_id}/generate", response_model=InsightReportListItem)
async def generate_insight(
    agent_id: str,
    req: GenerateInsightRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Trigger generation of an insight report for an agent."""
    agent = await resolve_prefix_id(Agent, agent_id, db)

    if current_user.org_id is not None and agent.owner_org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Agent does not belong to your organization")

    period_days = req.period_days if req else 14
    now = datetime.now(UTC)
    period_start = now - timedelta(days=period_days)

    report = InsightReport(
        agent_id=agent.id,
        triggered_by=current_user.id,
        status=InsightReportStatus.pending,
        period_start=period_start,
        period_end=now,
        started_at=now,
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

    return InsightReportResponse.model_validate(report)
