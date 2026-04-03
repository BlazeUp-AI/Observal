import logging
import uuid
from datetime import UTC

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from models.agent import Agent, AgentDownload, AgentStatus
from models.mcp import ListingStatus, McpDownload, McpListing
from models.user import User
from schemas.dashboard import AgentMetrics, McpMetrics, OverviewStats, TopItem, TrendPoint
from services.clickhouse import _query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["dashboard"])


async def _ch_json(sql: str, params: dict | None = None) -> list[dict]:
    """Run a ClickHouse query and return data rows."""
    try:
        r = await _query(f"{sql} FORMAT JSON", params)
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception as e:
        logger.warning(f"ClickHouse query failed: {e}")
    return []


@router.get("/mcps/{listing_id}/metrics", response_model=McpMetrics)
async def mcp_metrics(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dl_count = await db.scalar(select(func.count(McpDownload.id)).where(McpDownload.listing_id == listing_id)) or 0

    rows = await _ch_json(
        "SELECT "
        "count() as total_calls, "
        "countIf(status='error') as error_count, "
        "round(avg(latency_ms),1) as avg_latency, "
        "quantile(0.5)(latency_ms) as p50, "
        "quantile(0.9)(latency_ms) as p90, "
        "quantile(0.99)(latency_ms) as p99 "
        "FROM mcp_tool_calls WHERE mcp_server_id = {sid:String}",
        {"param_sid": str(listing_id)},
    )
    r = rows[0] if rows else {}
    total_calls = int(r.get("total_calls", 0))
    error_count = int(r.get("error_count", 0))

    return McpMetrics(
        listing_id=listing_id,
        total_downloads=dl_count,
        total_calls=total_calls,
        error_count=error_count,
        error_rate=round(error_count / total_calls, 4) if total_calls else 0,
        avg_latency_ms=float(r.get("avg_latency", 0)),
        p50_latency_ms=int(float(r.get("p50", 0))),
        p90_latency_ms=int(float(r.get("p90", 0))),
        p99_latency_ms=int(float(r.get("p99", 0))),
    )


@router.get("/agents/{agent_id}/metrics", response_model=AgentMetrics)
async def agent_metrics(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dl_count = await db.scalar(select(func.count(AgentDownload.id)).where(AgentDownload.agent_id == agent_id)) or 0

    rows = await _ch_json(
        "SELECT "
        "count() as total, "
        "countIf(user_action='accepted') as accepted, "
        "round(avg(tool_calls),1) as avg_tools, "
        "round(avg(latency_ms),1) as avg_latency "
        "FROM agent_interactions WHERE agent_id = {aid:String}",
        {"param_aid": str(agent_id)},
    )
    r = rows[0] if rows else {}
    total = int(r.get("total", 0))
    accepted = int(r.get("accepted", 0))

    return AgentMetrics(
        agent_id=agent_id,
        total_interactions=total,
        total_downloads=dl_count,
        acceptance_rate=round(accepted / total, 4) if total else 0,
        avg_tool_calls=float(r.get("avg_tools", 0)),
        avg_latency_ms=float(r.get("avg_latency", 0)),
    )


@router.get("/overview/stats", response_model=OverviewStats)
async def overview_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_mcps = (
        await db.scalar(select(func.count(McpListing.id)).where(McpListing.status == ListingStatus.approved)) or 0
    )
    total_agents = await db.scalar(select(func.count(Agent.id)).where(Agent.status == AgentStatus.active)) or 0
    total_users = await db.scalar(select(func.count(User.id))) or 0

    tool_rows = await _ch_json("SELECT count() as cnt FROM mcp_tool_calls WHERE timestamp > today()")
    agent_rows = await _ch_json("SELECT count() as cnt FROM agent_interactions WHERE timestamp > today()")

    return OverviewStats(
        total_mcps=total_mcps,
        total_agents=total_agents,
        total_users=total_users,
        total_tool_calls_today=int(tool_rows[0].get("cnt", 0)) if tool_rows else 0,
        total_agent_interactions_today=int(agent_rows[0].get("cnt", 0)) if agent_rows else 0,
    )


@router.get("/overview/top-mcps", response_model=list[TopItem])
async def top_mcps(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(McpDownload.listing_id, func.count(McpDownload.id).label("cnt"), McpListing.name)
        .join(McpListing, McpDownload.listing_id == McpListing.id)
        .group_by(McpDownload.listing_id, McpListing.name)
        .order_by(func.count(McpDownload.id).desc())
        .limit(5)
    )
    return [TopItem(id=row.listing_id, name=row.name, value=row.cnt) for row in result.all()]


@router.get("/overview/top-agents", response_model=list[TopItem])
async def top_agents(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(AgentDownload.agent_id, func.count(AgentDownload.id).label("cnt"), Agent.name)
        .join(Agent, AgentDownload.agent_id == Agent.id)
        .group_by(AgentDownload.agent_id, Agent.name)
        .order_by(func.count(AgentDownload.id).desc())
        .limit(5)
    )
    return [TopItem(id=row.agent_id, name=row.name, value=row.cnt) for row in result.all()]


@router.get("/overview/trends", response_model=list[TrendPoint])
async def trends(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from datetime import datetime as dt
    from datetime import timedelta

    now = dt.now(UTC)
    start = now - timedelta(days=30)

    day_col_mcp = func.date_trunc("day", McpListing.created_at).label("day")
    mcp_rows = await db.execute(
        select(day_col_mcp, func.count(McpListing.id).label("cnt"))
        .where(McpListing.created_at >= start)
        .group_by(day_col_mcp)
        .order_by(day_col_mcp)
    )

    day_col_user = func.date_trunc("day", User.created_at).label("day")
    user_rows = await db.execute(
        select(day_col_user, func.count(User.id).label("cnt"))
        .where(User.created_at >= start)
        .group_by(day_col_user)
        .order_by(day_col_user)
    )

    submissions = {str(r.day.date()): r.cnt for r in mcp_rows.all()}
    users = {str(r.day.date()): r.cnt for r in user_rows.all()}
    all_dates = sorted(set(list(submissions.keys()) + list(users.keys())))

    return [TrendPoint(date=d, submissions=submissions.get(d, 0), users=users.get(d, 0)) for d in all_dates]
