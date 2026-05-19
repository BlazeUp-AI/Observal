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

    return ExecConfigResponse(
        id=config.id,
        org_id=config.org_id,
        hourly_dev_cost=float(config.hourly_dev_cost),
        pre_ai_baselines=config.pre_ai_baselines or {},
        department_budgets=config.department_budgets or {},
        target_adoption_pct=config.target_adoption_pct,
        target_adoption_date=str(config.target_adoption_date) if config.target_adoption_date else None,
    )


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

    return ExecConfigResponse(
        id=config.id,
        org_id=config.org_id,
        hourly_dev_cost=float(config.hourly_dev_cost),
        pre_ai_baselines=config.pre_ai_baselines or {},
        department_budgets=config.department_budgets or {},
        target_adoption_pct=config.target_adoption_pct,
        target_adoption_date=str(config.target_adoption_date) if config.target_adoption_date else None,
    )
