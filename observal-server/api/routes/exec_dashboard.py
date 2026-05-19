# SPDX-License-Identifier: AGPL-3.0-only

"""Executive Dashboard API endpoints."""

import uuid
from datetime import UTC, timedelta
from datetime import datetime as dt

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_role
from api.routes.dashboard import _ch_json_scoped, _range_days
from config import settings
from models.agent import Agent, AgentTeamAccess, AgentVersion, AgentStatus
from models.download import AgentDownloadRecord
from models.exec_config import ExecDashboardConfig
from models.feedback import Feedback
from models.organization import Organization
from models.user import User, UserRole
from models.user_group import UserGroup

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/exec", tags=["exec-dashboard"])


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def compute_trend_percent(current: int, previous: int) -> float:
    """Compute period-over-period trend as a percentage."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def _period_bounds(range_: str | None) -> tuple[dt, dt, dt, dt]:
    """Return (current_start, current_end, previous_start, previous_end) for a range."""
    days = _range_days(range_)
    now = dt.now(UTC)
    current_start = now - timedelta(days=days)
    current_end = now
    previous_start = current_start - timedelta(days=days)
    previous_end = current_start
    return current_start, current_end, previous_start, previous_end


async def resolve_user_departments(db: AsyncSession, org_id: uuid.UUID | None) -> dict[str, list[str]]:
    """Return {department_name: [user_id_strings]} mapping.

    Priority: user_groups table (SSO) > users.department column (local-auth).
    Users with neither are grouped as 'Unassigned'.
    """
    dept_map: dict[str, list[str]] = {}
    assigned_user_ids: set[uuid.UUID] = set()

    # SSO groups
    if org_id:
        group_rows = (
            await db.execute(
                select(UserGroup.group_name, UserGroup.user_id)
                .join(User, UserGroup.user_id == User.id)
                .where(User.org_id == org_id)
            )
        ).all()
    else:
        group_rows = (await db.execute(select(UserGroup.group_name, UserGroup.user_id))).all()

    for row in group_rows:
        dept_map.setdefault(row.group_name, []).append(str(row.user_id))
        assigned_user_ids.add(row.user_id)

    # Fallback: users.department for users not in user_groups
    if org_id:
        dept_rows = (
            await db.execute(
                select(User.id, User.department)
                .where(User.org_id == org_id, User.department.isnot(None), User.id.notin_(assigned_user_ids) if assigned_user_ids else User.department.isnot(None))
            )
        ).all()
    else:
        dept_rows = (
            await db.execute(
                select(User.id, User.department)
                .where(User.department.isnot(None), User.id.notin_(assigned_user_ids) if assigned_user_ids else User.department.isnot(None))
            )
        ).all()

    for row in dept_rows:
        dept_map.setdefault(row.department, []).append(str(row.id))
        assigned_user_ids.add(row.id)

    # Unassigned users
    if org_id:
        all_users = (await db.execute(select(User.id).where(User.org_id == org_id))).scalars().all()
    else:
        all_users = (await db.execute(select(User.id))).scalars().all()

    unassigned = [str(uid) for uid in all_users if uid not in assigned_user_ids]
    if unassigned:
        dept_map["Unassigned"] = unassigned

    return dept_map


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ExecConfigResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    hourly_dev_cost: float
    pre_ai_baselines: dict
    department_budgets: dict
    target_adoption_pct: int
    target_adoption_date: str | None


class ExecConfigUpdate(BaseModel):
    hourly_dev_cost: float | None = None
    pre_ai_baselines: dict | None = None
    department_budgets: dict | None = None
    target_adoption_pct: int | None = None
    target_adoption_date: str | None = None


# ---------------------------------------------------------------------------
# Config endpoint
# ---------------------------------------------------------------------------


@router.get("/config", response_model=ExecConfigResponse | None)
async def get_exec_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Get exec dashboard configuration for the current org."""
    if not current_user.org_id:
        return None

    result = await db.execute(
        select(ExecDashboardConfig).where(ExecDashboardConfig.org_id == current_user.org_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return None

    return _config_to_response(config)


@router.put("/config", response_model=ExecConfigResponse)
async def update_exec_config(
    req: ExecConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Create or update exec dashboard configuration."""
    if not current_user.org_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    result = await db.execute(
        select(ExecDashboardConfig).where(ExecDashboardConfig.org_id == current_user.org_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        config = ExecDashboardConfig(org_id=current_user.org_id)
        db.add(config)

    if req.hourly_dev_cost is not None:
        config.hourly_dev_cost = req.hourly_dev_cost
    if req.pre_ai_baselines is not None:
        config.pre_ai_baselines = req.pre_ai_baselines
    if req.department_budgets is not None:
        config.department_budgets = req.department_budgets
    if req.target_adoption_pct is not None:
        config.target_adoption_pct = req.target_adoption_pct
    if req.target_adoption_date is not None:
        from datetime import date

        config.target_adoption_date = date.fromisoformat(req.target_adoption_date)

    await db.commit()
    await db.refresh(config)

    return _config_to_response(config)


def _config_to_response(config: ExecDashboardConfig) -> ExecConfigResponse:
    return ExecConfigResponse(
        id=config.id,
        org_id=config.org_id,
        hourly_dev_cost=float(config.hourly_dev_cost),
        pre_ai_baselines=config.pre_ai_baselines or {},
        department_budgets=config.department_budgets or {},
        target_adoption_pct=config.target_adoption_pct,
        target_adoption_date=str(config.target_adoption_date) if config.target_adoption_date else None,
    )


# ---------------------------------------------------------------------------
# Adoption Tab
# ---------------------------------------------------------------------------


class AdoptionPoint(BaseModel):
    month: str
    adoption_pct: float


class AdoptionResponse(BaseModel):
    monthly: list[AdoptionPoint]
    current_pct: float
    total_users: int
    active_users: int
    departments_covered: int


@router.get("/adoption", response_model=AdoptionResponse)
async def get_adoption(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Monthly AI adoption % (active users with traces / total users)."""
    org_id = current_user.org_id

    # Total users in org
    user_stmt = select(func.count(User.id))
    if org_id:
        user_stmt = user_stmt.where(User.org_id == org_id)
    total_users = await db.scalar(user_stmt) or 0

    # Monthly active users from ClickHouse (last 12 months)
    rows = await _ch_json_scoped(
        "SELECT toStartOfMonth(start_time) AS month, count(DISTINCT user_id) AS active "
        "FROM traces FINAL WHERE project_id = 'default' AND is_deleted = 0 "
        "AND start_time >= now() - INTERVAL 12 MONTH "
        "GROUP BY month ORDER BY month",
        current_user,
    )

    monthly = []
    for r in rows:
        active = int(r.get("active", 0))
        pct = round((active / total_users) * 100, 1) if total_users > 0 else 0.0
        monthly.append(AdoptionPoint(month=str(r["month"])[:7], adoption_pct=pct))

    # Current month active users
    current_rows = await _ch_json_scoped(
        "SELECT count(DISTINCT user_id) AS active "
        "FROM traces FINAL WHERE project_id = 'default' AND is_deleted = 0 "
        "AND start_time >= toStartOfMonth(now())",
        current_user,
    )
    active_users = int(current_rows[0]["active"]) if current_rows else 0
    current_pct = round((active_users / total_users) * 100, 1) if total_users > 0 else 0.0

    # Departments covered (groups with at least one active user)
    dept_map = await resolve_user_departments(db, org_id)
    departments_covered = sum(1 for k in dept_map if k != "Unassigned")

    return AdoptionResponse(
        monthly=monthly,
        current_pct=current_pct,
        total_users=total_users,
        active_users=active_users,
        departments_covered=departments_covered,
    )


class AgentCountBreakdown(BaseModel):
    total: int
    active: int
    published: int
    in_development: int
    by_category: list[dict]


@router.get("/agent-counts", response_model=AgentCountBreakdown)
async def get_agent_counts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Agent count breakdown by status and category."""
    org_id = current_user.org_id

    base = select(Agent)
    if org_id:
        base = base.where(Agent.owner_org_id == org_id)

    # Total
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0

    # Published (approved latest version)
    pub_stmt = (
        select(func.count(Agent.id))
        .join(AgentVersion, Agent.latest_version_id == AgentVersion.id)
        .where(AgentVersion.status == AgentStatus.approved)
    )
    if org_id:
        pub_stmt = pub_stmt.where(Agent.owner_org_id == org_id)
    published = await db.scalar(pub_stmt) or 0

    # In development (pending/draft)
    dev_stmt = (
        select(func.count(Agent.id))
        .join(AgentVersion, Agent.latest_version_id == AgentVersion.id)
        .where(AgentVersion.status.in_([AgentStatus.pending, AgentStatus.draft]))
    )
    if org_id:
        dev_stmt = dev_stmt.where(Agent.owner_org_id == org_id)
    in_development = await db.scalar(dev_stmt) or 0

    # Active (had traces in last 7 days) — from ClickHouse
    active_rows = await _ch_json_scoped(
        "SELECT count(DISTINCT agent_id) AS cnt FROM traces FINAL "
        "WHERE project_id = 'default' AND is_deleted = 0 "
        "AND agent_id != '' AND start_time >= now() - INTERVAL 7 DAY",
        current_user,
    )
    active = int(active_rows[0]["cnt"]) if active_rows else 0

    # By category
    cat_stmt = select(Agent.category, func.count(Agent.id)).group_by(Agent.category)
    if org_id:
        cat_stmt = cat_stmt.where(Agent.owner_org_id == org_id)
    cat_rows = (await db.execute(cat_stmt)).all()
    by_category = [
        {"category": row[0] or "Uncategorized", "count": row[1]}
        for row in cat_rows
    ]

    return AgentCountBreakdown(
        total=total,
        active=active,
        published=published,
        in_development=in_development,
        by_category=by_category,
    )


class UsageByCategoryItem(BaseModel):
    category: str
    sessions: int
    growth_pct: float


@router.get("/usage-by-category", response_model=list[UsageByCategoryItem])
async def get_usage_by_category(
    range_: str | None = Query(None, alias="range"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Agent usage grouped by category with period-over-period growth."""
    days = _range_days(range_)

    # Current period sessions by agent
    current_rows = await _ch_json_scoped(
        "SELECT agent_id, count() AS cnt FROM traces FINAL "
        "WHERE project_id = 'default' AND is_deleted = 0 AND agent_id != '' "
        "AND start_time >= now() - INTERVAL {days:UInt32} DAY "
        "GROUP BY agent_id",
        current_user,
        {"param_days": str(days)},
    )

    # Previous period
    prev_rows = await _ch_json_scoped(
        "SELECT agent_id, count() AS cnt FROM traces FINAL "
        "WHERE project_id = 'default' AND is_deleted = 0 AND agent_id != '' "
        "AND start_time >= now() - INTERVAL {days2:UInt32} DAY "
        "AND start_time < now() - INTERVAL {days:UInt32} DAY "
        "GROUP BY agent_id",
        current_user,
        {"param_days": str(days), "param_days2": str(days * 2)},
    )

    # Resolve agent_id → category from PG
    agent_ids = list({r["agent_id"] for r in current_rows + prev_rows if r.get("agent_id")})
    cat_map: dict[str, str] = {}
    if agent_ids:
        import uuid as _uuid

        valid_ids = []
        for aid in agent_ids:
            try:
                valid_ids.append(_uuid.UUID(aid))
            except (ValueError, AttributeError):
                pass
        if valid_ids:
            rows = (await db.execute(select(Agent.id, Agent.category).where(Agent.id.in_(valid_ids)))).all()
            cat_map = {str(r.id): r.category or "Uncategorized" for r in rows}

    # Aggregate by category
    current_by_cat: dict[str, int] = {}
    for r in current_rows:
        cat = cat_map.get(r["agent_id"], "Uncategorized")
        current_by_cat[cat] = current_by_cat.get(cat, 0) + int(r["cnt"])

    prev_by_cat: dict[str, int] = {}
    for r in prev_rows:
        cat = cat_map.get(r["agent_id"], "Uncategorized")
        prev_by_cat[cat] = prev_by_cat.get(cat, 0) + int(r["cnt"])

    result = []
    for cat, sessions in sorted(current_by_cat.items(), key=lambda x: -x[1]):
        prev = prev_by_cat.get(cat, 0)
        growth = compute_trend_percent(sessions, prev)
        result.append(UsageByCategoryItem(category=cat, sessions=sessions, growth_pct=growth))

    return result


class PlatformCoverageItem(BaseModel):
    platform: str
    users: int
    sessions: int


@router.get("/platform-coverage", response_model=list[PlatformCoverageItem])
async def get_platform_coverage(
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """IDE/platform coverage — distinct users and sessions per platform."""
    rows = await _ch_json_scoped(
        "SELECT ide, count(DISTINCT user_id) AS users, count() AS sessions "
        "FROM traces FINAL WHERE project_id = 'default' AND is_deleted = 0 "
        "AND ide != '' "
        "GROUP BY ide ORDER BY sessions DESC",
        current_user,
    )
    return [
        PlatformCoverageItem(platform=r["ide"], users=int(r["users"]), sessions=int(r["sessions"]))
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Investments Tab (Platform Comparison)
# ---------------------------------------------------------------------------


class PlatformScore(BaseModel):
    platform: str
    composite_score: float
    sessions: int
    avg_cost: float
    avg_latency_ms: float
    success_rate: float
    error_rate: float
    users: int


@router.get("/platforms", response_model=list[PlatformScore])
async def get_platforms(
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Per-IDE platform comparison with composite scores."""
    rows = await _ch_json_scoped(
        "SELECT t.ide AS ide, "
        "count(DISTINCT t.trace_id) AS sessions, "
        "count(DISTINCT t.user_id) AS users, "
        "round(avg(s.cost), 4) AS avg_cost, "
        "round(avg(s.latency_ms), 1) AS avg_latency_ms, "
        "countIf(s.status = 'error') AS errors, "
        "count(s.span_id) AS total_spans "
        "FROM traces AS t FINAL "
        "INNER JOIN spans AS s FINAL ON t.trace_id = s.trace_id "
        "AND s.project_id = 'default' AND s.is_deleted = 0 "
        "WHERE t.project_id = 'default' AND t.is_deleted = 0 AND t.ide != '' "
        "GROUP BY t.ide ORDER BY sessions DESC",
        current_user,
    )

    if not rows:
        return []

    # Compute normalized scores for composite
    max_sessions = max(int(r.get("sessions", 1)) for r in rows) or 1
    results = []
    for r in rows:
        sessions = int(r.get("sessions", 0))
        users = int(r.get("users", 0))
        avg_cost = float(r.get("avg_cost") or 0)
        avg_latency = float(r.get("avg_latency_ms") or 0)
        errors = int(r.get("errors", 0))
        total_spans = int(r.get("total_spans", 1)) or 1

        error_rate = round(errors / total_spans, 4)
        success_rate = round(1 - error_rate, 4)

        # Normalized 0-100 components
        success_score = success_rate * 100
        cost_score = max(0, 100 - (avg_cost * 1000)) if avg_cost > 0 else 100
        speed_score = max(0, 100 - (avg_latency / 50)) if avg_latency > 0 else 100
        volume_score = (sessions / max_sessions) * 100

        composite = round(
            success_score * 0.30 + cost_score * 0.25 + speed_score * 0.25 + volume_score * 0.20,
            1,
        )

        results.append(PlatformScore(
            platform=r["ide"],
            composite_score=min(composite, 100),
            sessions=sessions,
            avg_cost=avg_cost,
            avg_latency_ms=avg_latency,
            success_rate=round(success_rate * 100, 1),
            error_rate=round(error_rate * 100, 2),
            users=users,
        ))

    return results


# ---------------------------------------------------------------------------
# Velocity Tab
# ---------------------------------------------------------------------------


class VelocityPoint(BaseModel):
    week: str
    traces: int


class VelocityResponse(BaseModel):
    weekly: list[VelocityPoint]
    current_weekly_avg: float
    baseline_weekly_avg: float
    multiplier: float


@router.get("/velocity", response_model=VelocityResponse)
async def get_velocity(
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Weekly trace counts with baseline comparison."""
    rows = await _ch_json_scoped(
        "SELECT toStartOfWeek(start_time) AS week, count() AS traces "
        "FROM traces FINAL WHERE project_id = 'default' AND is_deleted = 0 "
        "AND start_time >= now() - INTERVAL 12 WEEK "
        "GROUP BY week ORDER BY week",
        current_user,
    )

    weekly = [VelocityPoint(week=str(r["week"])[:10], traces=int(r["traces"])) for r in rows]

    if len(weekly) >= 4:
        baseline_weeks = weekly[:4]
        current_weeks = weekly[-4:]
        baseline_avg = sum(w.traces for w in baseline_weeks) / len(baseline_weeks)
        current_avg = sum(w.traces for w in current_weeks) / len(current_weeks)
    elif weekly:
        baseline_avg = weekly[0].traces
        current_avg = weekly[-1].traces
    else:
        baseline_avg = 0
        current_avg = 0

    multiplier = round(current_avg / baseline_avg, 1) if baseline_avg > 0 else 0.0

    return VelocityResponse(
        weekly=weekly,
        current_weekly_avg=round(current_avg, 1),
        baseline_weekly_avg=round(baseline_avg, 1),
        multiplier=multiplier,
    )


class TopAgentScored(BaseModel):
    id: str
    name: str
    category: str
    composite_score: float
    sessions: int
    downloads: int
    avg_rating: float | None
    weekly_trend: list[int]


@router.get("/top-agents", response_model=list[TopAgentScored])
async def get_top_agents(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Top agents by composite score (downloads + sessions + rating)."""
    org_id = current_user.org_id

    # Downloads from PG
    dl_stmt = (
        select(AgentDownloadRecord.agent_id, func.count(AgentDownloadRecord.id).label("downloads"))
        .group_by(AgentDownloadRecord.agent_id)
    )
    dl_rows = (await db.execute(dl_stmt)).all()
    dl_map = {str(r.agent_id): r.downloads for r in dl_rows}

    # Ratings from PG
    rating_stmt = (
        select(Feedback.listing_id, func.avg(Feedback.rating).label("avg_rating"))
        .where(Feedback.listing_type == "agent")
        .group_by(Feedback.listing_id)
    )
    rating_rows = (await db.execute(rating_stmt)).all()
    rating_map = {str(r.listing_id): round(float(r.avg_rating), 2) for r in rating_rows}

    # Sessions from ClickHouse (last 30 days)
    session_rows = await _ch_json_scoped(
        "SELECT agent_id, count() AS sessions "
        "FROM traces FINAL WHERE project_id = 'default' AND is_deleted = 0 "
        "AND agent_id != '' AND start_time >= now() - INTERVAL 30 DAY "
        "GROUP BY agent_id ORDER BY sessions DESC LIMIT 50",
        current_user,
    )
    session_map = {r["agent_id"]: int(r["sessions"]) for r in session_rows}

    # Weekly trend (last 6 weeks) per agent
    trend_rows = await _ch_json_scoped(
        "SELECT agent_id, toStartOfWeek(start_time) AS week, count() AS cnt "
        "FROM traces FINAL WHERE project_id = 'default' AND is_deleted = 0 "
        "AND agent_id != '' AND start_time >= now() - INTERVAL 6 WEEK "
        "GROUP BY agent_id, week ORDER BY agent_id, week",
        current_user,
    )
    trend_map: dict[str, list[int]] = {}
    for r in trend_rows:
        aid = r["agent_id"]
        trend_map.setdefault(aid, []).append(int(r["cnt"]))

    # Get all candidate agent_ids
    all_agent_ids = set(session_map.keys()) | set(dl_map.keys())
    if not all_agent_ids:
        return []

    # Resolve names + categories from PG
    import uuid as _uuid

    valid_ids = []
    for aid in all_agent_ids:
        try:
            valid_ids.append(_uuid.UUID(aid))
        except (ValueError, AttributeError):
            pass

    agent_info: dict[str, tuple[str, str]] = {}
    if valid_ids:
        info_stmt = select(Agent.id, Agent.name, Agent.category)
        if org_id:
            info_stmt = info_stmt.where(Agent.owner_org_id == org_id)
        info_stmt = info_stmt.where(Agent.id.in_(valid_ids))
        info_rows = (await db.execute(info_stmt)).all()
        agent_info = {str(r.id): (r.name, r.category or "Uncategorized") for r in info_rows}

    # Compute composite and rank
    max_downloads = max(dl_map.values(), default=1) or 1
    max_sessions = max(session_map.values(), default=1) or 1

    scored = []
    for aid, (name, category) in agent_info.items():
        downloads = dl_map.get(aid, 0)
        sessions = session_map.get(aid, 0)
        rating = rating_map.get(aid)

        dl_norm = (downloads / max_downloads) * 100
        sess_norm = (sessions / max_sessions) * 100
        rating_norm = ((rating or 0) / 5) * 100

        composite = round(dl_norm * 0.3 + sess_norm * 0.4 + rating_norm * 0.3, 1)

        scored.append(TopAgentScored(
            id=aid,
            name=name,
            category=category,
            composite_score=composite,
            sessions=sessions,
            downloads=downloads,
            avg_rating=rating,
            weekly_trend=trend_map.get(aid, []),
        ))

    scored.sort(key=lambda x: -x.composite_score)
    return scored[:limit]


# ---------------------------------------------------------------------------
# Departments Tab
# ---------------------------------------------------------------------------


class DepartmentItem(BaseModel):
    department: str
    user_count: int
    agent_count: int
    utilization_pct: float
    sessions_per_user: float


class DepartmentsResponse(BaseModel):
    departments: list[DepartmentItem]


@router.get("/departments", response_model=DepartmentsResponse)
async def get_departments(
    range_: str | None = Query(None, alias="range"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Per-department breakdown: users, agents, utilization, sessions/user."""
    org_id = current_user.org_id
    days = _range_days(range_)

    dept_map = await resolve_user_departments(db, org_id)
    if not dept_map:
        return DepartmentsResponse(departments=[])

    # Agent count per department (via AgentTeamAccess)
    agent_access_rows = (
        await db.execute(
            select(AgentTeamAccess.group_name, func.count(AgentTeamAccess.agent_id.distinct()))
            .group_by(AgentTeamAccess.group_name)
        )
    ).all()
    agent_count_by_dept: dict[str, int] = {r[0]: r[1] for r in agent_access_rows}

    # Get trace counts per user from ClickHouse
    all_user_ids = []
    for uids in dept_map.values():
        all_user_ids.extend(uids)

    user_sessions: dict[str, int] = {}
    if all_user_ids:
        # Batch query — get session count per user in period
        session_rows = await _ch_json_scoped(
            "SELECT user_id, count() AS sessions "
            "FROM traces FINAL WHERE project_id = 'default' AND is_deleted = 0 "
            "AND start_time >= now() - INTERVAL {days:UInt32} DAY "
            "GROUP BY user_id",
            current_user,
            {"param_days": str(days)},
        )
        user_sessions = {r["user_id"]: int(r["sessions"]) for r in session_rows}

    departments = []
    for dept_name, user_ids in sorted(dept_map.items()):
        user_count = len(user_ids)
        agent_count = agent_count_by_dept.get(dept_name, 0)

        # Utilization: users with >= 1 session in period
        active_in_dept = sum(1 for uid in user_ids if user_sessions.get(uid, 0) > 0)
        utilization = round((active_in_dept / user_count) * 100, 1) if user_count > 0 else 0.0

        # Sessions per user
        total_sessions = sum(user_sessions.get(uid, 0) for uid in user_ids)
        sessions_per_user = round(total_sessions / user_count, 1) if user_count > 0 else 0.0

        departments.append(DepartmentItem(
            department=dept_name,
            user_count=user_count,
            agent_count=agent_count,
            utilization_pct=utilization,
            sessions_per_user=sessions_per_user,
        ))

    return DepartmentsResponse(departments=departments)


class DeptTokenItem(BaseModel):
    department: str
    tokens_used: int
    cost_per_task: float
    sessions_per_user: float
    trend_pct: float


@router.get("/dept-tokens", response_model=list[DeptTokenItem])
async def get_dept_tokens(
    range_: str | None = Query(None, alias="range"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Token usage and cost per department with trend."""
    org_id = current_user.org_id
    days = _range_days(range_)

    dept_map = await resolve_user_departments(db, org_id)
    if not dept_map:
        return []

    # Current period: tokens + cost per user
    current_rows = await _ch_json_scoped(
        "SELECT s.user_id AS user_id, "
        "sumIf(s.token_count_total, s.token_count_total IS NOT NULL) AS tokens, "
        "count(DISTINCT t.trace_id) AS traces, "
        "sum(s.cost) AS total_cost "
        "FROM spans AS s FINAL "
        "INNER JOIN traces AS t FINAL ON s.trace_id = t.trace_id "
        "AND t.project_id = 'default' AND t.is_deleted = 0 "
        "WHERE s.project_id = 'default' AND s.is_deleted = 0 "
        "AND s.start_time >= now() - INTERVAL {days:UInt32} DAY "
        "GROUP BY s.user_id",
        current_user,
        {"param_days": str(days)},
    )
    current_by_user: dict[str, dict] = {
        r["user_id"]: {"tokens": int(r["tokens"]), "traces": int(r["traces"]), "cost": float(r.get("total_cost") or 0)}
        for r in current_rows
    }

    # Previous period: tokens per user (for trend)
    prev_rows = await _ch_json_scoped(
        "SELECT s.user_id AS user_id, "
        "sumIf(s.token_count_total, s.token_count_total IS NOT NULL) AS tokens "
        "FROM spans AS s FINAL "
        "WHERE s.project_id = 'default' AND s.is_deleted = 0 "
        "AND s.start_time >= now() - INTERVAL {days2:UInt32} DAY "
        "AND s.start_time < now() - INTERVAL {days:UInt32} DAY "
        "GROUP BY s.user_id",
        current_user,
        {"param_days": str(days), "param_days2": str(days * 2)},
    )
    prev_by_user: dict[str, int] = {r["user_id"]: int(r["tokens"]) for r in prev_rows}

    result = []
    for dept_name, user_ids in sorted(dept_map.items()):
        user_count = len(user_ids)
        tokens = sum(current_by_user.get(uid, {}).get("tokens", 0) for uid in user_ids)
        traces = sum(current_by_user.get(uid, {}).get("traces", 0) for uid in user_ids)
        cost = sum(current_by_user.get(uid, {}).get("cost", 0) for uid in user_ids)
        prev_tokens = sum(prev_by_user.get(uid, 0) for uid in user_ids)

        cost_per_task = round(cost / traces, 4) if traces > 0 else 0.0
        sessions_per_user = round(traces / user_count, 1) if user_count > 0 else 0.0
        trend = compute_trend_percent(tokens, prev_tokens)

        result.append(DeptTokenItem(
            department=dept_name,
            tokens_used=tokens,
            cost_per_task=cost_per_task,
            sessions_per_user=sessions_per_user,
            trend_pct=trend,
        ))

    return result


# ---------------------------------------------------------------------------
# Cost Intelligence Tab
# ---------------------------------------------------------------------------


class MonthlyCostPoint(BaseModel):
    month: str
    ai_spend: float
    savings: float


class CostByCategory(BaseModel):
    category: str
    baseline_cost: float
    actual_cost: float
    saved_pct: float


class CostSummaryResponse(BaseModel):
    monthly_savings: float
    cost_reduction_pct: float
    projected_annual_savings: float
    cost_per_task: float
    monthly_trend: list[MonthlyCostPoint]
    by_category: list[CostByCategory]
    configured: bool


@router.get("/cost-summary", response_model=CostSummaryResponse)
async def get_cost_summary(
    range_: str | None = Query(None, alias="range"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Cost savings, spend, and ROI. Requires exec_dashboard_config baselines."""
    org_id = current_user.org_id
    days = _range_days(range_)

    # Load config
    config = None
    if org_id:
        result = await db.execute(
            select(ExecDashboardConfig).where(ExecDashboardConfig.org_id == org_id)
        )
        config = result.scalar_one_or_none()

    if not config:
        return CostSummaryResponse(
            monthly_savings=0,
            cost_reduction_pct=0,
            projected_annual_savings=0,
            cost_per_task=0,
            monthly_trend=[],
            by_category=[],
            configured=False,
        )

    baselines = config.pre_ai_baselines or {}

    # Monthly AI spend from ClickHouse
    monthly_rows = await _ch_json_scoped(
        "SELECT toStartOfMonth(start_time) AS month, "
        "sum(cost) AS spend, count(DISTINCT trace_id) AS traces "
        "FROM spans FINAL WHERE project_id = 'default' AND is_deleted = 0 "
        "AND start_time >= now() - INTERVAL 12 MONTH "
        "AND cost IS NOT NULL AND cost > 0 "
        "GROUP BY month ORDER BY month",
        current_user,
    )

    # Compute average baseline cost (mean of all category baselines)
    avg_baseline = sum(baselines.values()) / len(baselines) if baselines else 0

    monthly_trend = []
    total_spend = 0.0
    total_traces = 0
    for r in monthly_rows:
        spend = float(r.get("spend") or 0)
        traces = int(r.get("traces") or 0)
        savings = max(0, (avg_baseline * traces) - spend) if avg_baseline > 0 else 0
        monthly_trend.append(MonthlyCostPoint(
            month=str(r["month"])[:7],
            ai_spend=round(spend, 2),
            savings=round(savings, 2),
        ))
        total_spend += spend
        total_traces += traces

    # Current month stats
    current_month = monthly_trend[-1] if monthly_trend else None
    monthly_savings = current_month.savings if current_month else 0
    cost_per_task = round(total_spend / total_traces, 4) if total_traces > 0 else 0

    # Cost reduction %
    baseline_total = avg_baseline * total_traces if avg_baseline > 0 else 0
    cost_reduction_pct = round(((baseline_total - total_spend) / baseline_total) * 100, 1) if baseline_total > 0 else 0

    # Projected annual (latest month × 12)
    projected_annual = round(monthly_savings * 12, 2)

    # Cost by category
    cat_rows = await _ch_json_scoped(
        "SELECT t.agent_id AS agent_id, "
        "round(avg(s.cost), 4) AS avg_cost, count(DISTINCT t.trace_id) AS traces "
        "FROM spans AS s FINAL "
        "INNER JOIN traces AS t FINAL ON s.trace_id = t.trace_id "
        "AND t.project_id = 'default' AND t.is_deleted = 0 "
        "WHERE s.project_id = 'default' AND s.is_deleted = 0 "
        "AND s.cost IS NOT NULL AND s.cost > 0 "
        "AND t.agent_id != '' "
        "AND s.start_time >= now() - INTERVAL {days:UInt32} DAY "
        "GROUP BY t.agent_id",
        current_user,
        {"param_days": str(days)},
    )

    # Resolve agent categories
    agent_ids = [r["agent_id"] for r in cat_rows if r.get("agent_id")]
    cat_map: dict[str, str] = {}
    if agent_ids:
        import uuid as _uuid

        valid_ids = []
        for aid in agent_ids:
            try:
                valid_ids.append(_uuid.UUID(aid))
            except (ValueError, AttributeError):
                pass
        if valid_ids:
            rows = (await db.execute(select(Agent.id, Agent.category).where(Agent.id.in_(valid_ids)))).all()
            cat_map = {str(r.id): r.category or "Uncategorized" for r in rows}

    # Aggregate cost by category
    cost_by_cat: dict[str, list[float]] = {}
    for r in cat_rows:
        cat = cat_map.get(r["agent_id"], "Uncategorized")
        cost_by_cat.setdefault(cat, []).append(float(r.get("avg_cost") or 0))

    by_category = []
    for cat, costs in sorted(cost_by_cat.items()):
        actual = round(sum(costs) / len(costs), 4) if costs else 0
        baseline = baselines.get(cat, avg_baseline)
        saved = round(((baseline - actual) / baseline) * 100, 1) if baseline > 0 else 0
        by_category.append(CostByCategory(
            category=cat,
            baseline_cost=round(baseline, 2),
            actual_cost=actual,
            saved_pct=max(saved, 0),
        ))

    return CostSummaryResponse(
        monthly_savings=round(monthly_savings, 2),
        cost_reduction_pct=cost_reduction_pct,
        projected_annual_savings=projected_annual,
        cost_per_task=cost_per_task,
        monthly_trend=monthly_trend,
        by_category=by_category,
        configured=True,
    )
