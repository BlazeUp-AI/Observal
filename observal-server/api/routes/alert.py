import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_role
from models.alert import AlertRule
from models.user import User, UserRole
from schemas.alert import AlertRuleCreate, AlertRuleResponse, AlertRuleUpdate

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertRuleResponse])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    # Admins see all alerts; regular users only see their own
    stmt = select(AlertRule).order_by(AlertRule.created_at.desc())
    if current_user.role != UserRole.admin:
        stmt = stmt.where(AlertRule.created_by == current_user.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=AlertRuleResponse, status_code=201)
async def create_alert(
    body: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    rule = AlertRule(
        name=body.name,
        metric=body.metric,
        threshold=body.threshold,
        condition=body.condition,
        target_type=body.target_type,
        target_id=body.target_id if body.target_type != "all" else "",
        webhook_url=body.webhook_url,
        created_by=current_user.id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.patch("/{alert_id}", response_model=AlertRuleResponse)
async def update_alert(
    alert_id: uuid.UUID,
    body: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    rule = await db.get(AlertRule, alert_id)
    if not rule:
        raise HTTPException(404, "Alert rule not found")
    if rule.created_by != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(403, "Not authorized to modify this alert rule")
    rule.status = body.status
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    rule = await db.get(AlertRule, alert_id)
    if not rule:
        raise HTTPException(404, "Alert rule not found")
    if rule.created_by != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(403, "Not authorized to delete this alert rule")
    await db.delete(rule)
    await db.commit()
