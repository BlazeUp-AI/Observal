import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import ROLE_HIERARCHY, get_db, require_role
from models.alert import AlertRule
from models.alert_history import AlertHistory
from models.user import User, UserRole
from schemas.alert import AlertHistoryResponse, AlertRuleCreate, AlertRuleResponse, AlertRuleUpdate
from services.alert_evaluator import is_private_url

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _validate_webhook_url(url: str) -> None:
    if not url:
        return  # empty URL is OK (no webhook)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "webhook_url must use http or https")
    if is_private_url(url):
        raise HTTPException(400, "webhook_url must not point to private/internal networks")


@router.get("", response_model=list[AlertRuleResponse])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    stmt = select(AlertRule).order_by(AlertRule.created_at.desc())
    if ROLE_HIERARCHY.get(current_user.role, 999) > ROLE_HIERARCHY[UserRole.admin]:
        stmt = stmt.where(AlertRule.created_by == current_user.id)
    elif current_user.org_id is not None:
        # Admin sees all alerts within their org (filter through user table)
        org_user_ids = select(User.id).where(User.org_id == current_user.org_id)
        stmt = stmt.where(AlertRule.created_by.in_(org_user_ids))
    # else: admin with no org (local mode) — no filter, sees everything
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=AlertRuleResponse, status_code=201)
async def create_alert(
    body: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    _validate_webhook_url(body.webhook_url)
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
    # Org-scope check: ensure the alert belongs to the user's org
    if current_user.org_id is not None:
        creator = (await db.execute(select(User).where(User.id == rule.created_by))).scalar_one_or_none()
        if not creator or creator.org_id != current_user.org_id:
            raise HTTPException(404, "Alert rule not found")
    is_admin_or_above = ROLE_HIERARCHY.get(current_user.role, 999) <= ROLE_HIERARCHY[UserRole.admin]
    if rule.created_by != current_user.id and not is_admin_or_above:
        raise HTTPException(403, "Not authorized to modify this alert rule")
    if body.status is not None:
        rule.status = body.status
    if body.webhook_url is not None:
        _validate_webhook_url(body.webhook_url)
        rule.webhook_url = body.webhook_url
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
    # Org-scope check: ensure the alert belongs to the user's org
    if current_user.org_id is not None:
        creator = (await db.execute(select(User).where(User.id == rule.created_by))).scalar_one_or_none()
        if not creator or creator.org_id != current_user.org_id:
            raise HTTPException(404, "Alert rule not found")
    is_admin_or_above = ROLE_HIERARCHY.get(current_user.role, 999) <= ROLE_HIERARCHY[UserRole.admin]
    if rule.created_by != current_user.id and not is_admin_or_above:
        raise HTTPException(403, "Not authorized to delete this alert rule")
    await db.delete(rule)
    await db.commit()


@router.get("/{alert_id}/history", response_model=list[AlertHistoryResponse])
async def get_alert_history(
    alert_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    rule = await db.get(AlertRule, alert_id)
    if not rule:
        raise HTTPException(404, "Alert rule not found")
    # Org-scope check: ensure the alert belongs to the user's org
    if current_user.org_id is not None:
        creator = (await db.execute(select(User).where(User.id == rule.created_by))).scalar_one_or_none()
        if not creator or creator.org_id != current_user.org_id:
            raise HTTPException(404, "Alert rule not found")
    is_admin = ROLE_HIERARCHY.get(current_user.role, 999) <= ROLE_HIERARCHY[UserRole.admin]
    if rule.created_by != current_user.id and not is_admin:
        raise HTTPException(403, "Not authorized")

    stmt = (
        select(AlertHistory)
        .where(AlertHistory.alert_rule_id == alert_id)
        .order_by(AlertHistory.fired_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
