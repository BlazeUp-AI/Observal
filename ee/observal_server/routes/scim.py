"""SCIM 2.0 provisioning endpoints for enterprise deployments."""

from __future__ import annotations

import logging
import uuid as _uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_or_create_default_org
from ee.observal_server.services.scim_service import (
    format_scim_error,
    format_scim_list,
    format_scim_user,
    hash_scim_token,
    parse_scim_user,
)
from models.scim_token import ScimToken
from models.user import User, UserRole
from services.audit_helpers import audit
from services.events import UserCreated, UserDeleted, bus
from services.security_events import (
    EventType,
    SecurityEvent,
    Severity,
    emit_security_event,
)

logger = logging.getLogger("observal.ee.scim")

router = APIRouter(prefix="/api/v1/scim", tags=["enterprise-scim"])

SCIM_CONTENT_TYPE = "application/scim+json"


async def _verify_scim_token(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> ScimToken:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid SCIM bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    token_hash = hash_scim_token(token)

    result = await db.execute(
        select(ScimToken).where(
            ScimToken.token_hash == token_hash,
            ScimToken.active.is_(True),
        )
    )
    scim_token = result.scalar_one_or_none()
    if not scim_token:
        await emit_security_event(
            SecurityEvent(
                event_type=EventType.API_KEY_REJECTED,
                severity=Severity.WARNING,
                outcome="failure",
                detail="Invalid SCIM bearer token",
            )
        )
        raise HTTPException(status_code=401, detail="Invalid SCIM bearer token")
    return scim_token


@router.get("/Users")
async def list_users(
    request: Request,
    startIndex: int = 1,  # noqa: N803 - SCIM spec parameter name
    count: int = 100,
    filter: str | None = None,
    scim_token: ScimToken = Depends(_verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    base_url = str(request.base_url).rstrip("/") + "/api/v1/scim"

    if filter and "userName eq" in filter:
        email = filter.split('"')[1].strip().lower() if '"' in filter else ""
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            resources = [format_scim_user(user, base_url)] if user else []
            return JSONResponse(
                content=format_scim_list(resources, len(resources), startIndex),
                media_type=SCIM_CONTENT_TYPE,
            )

    base_q = select(User)
    if scim_token.org_id:
        base_q = base_q.where(User.org_id == scim_token.org_id)

    total_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    users_q = base_q.order_by(User.created_at).offset(startIndex - 1).limit(count)
    result = await db.execute(users_q)
    users = list(result.scalars().all())

    resources = [format_scim_user(u, base_url) for u in users]
    return JSONResponse(
        content=format_scim_list(resources, total, startIndex),
        media_type=SCIM_CONTENT_TYPE,
    )


@router.post("/Users", status_code=201)
async def create_user(
    request: Request,
    scim_token: ScimToken = Depends(_verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    parsed = parse_scim_user(body)
    email = parsed["email"]
    if not email:
        return JSONResponse(
            status_code=400,
            content=format_scim_error(400, "userName or email is required"),
            media_type=SCIM_CONTENT_TYPE,
        )

    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        return JSONResponse(
            status_code=409,
            content=format_scim_error(409, f"User with email {email} already exists"),
            media_type=SCIM_CONTENT_TYPE,
        )

    default_org = await get_or_create_default_org(db)
    org_id = scim_token.org_id or default_org.id

    user = User(
        email=email,
        name=parsed["name"],
        role=UserRole.user,
        org_id=org_id,
        auth_provider="scim",
    )
    db.add(user)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return JSONResponse(
            status_code=409,
            content=format_scim_error(409, f"User with email {email} already exists"),
            media_type=SCIM_CONTENT_TYPE,
        )

    await db.commit()
    await bus.emit(UserCreated(user_id=str(user.id), email=user.email, role=user.role.value))
    await audit(
        None,
        "scim.user.create",
        resource_type="user",
        resource_id=str(user.id),
        detail=f"SCIM provisioned: {email}",
    )

    base_url = str(request.base_url).rstrip("/") + "/api/v1/scim"
    return JSONResponse(
        status_code=201,
        content=format_scim_user(user, base_url),
        media_type=SCIM_CONTENT_TYPE,
    )


@router.get("/Users/{user_id}")
async def get_user(
    user_id: str,
    request: Request,
    scim_token: ScimToken = Depends(_verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = _uuid.UUID(user_id)
    except ValueError:
        return JSONResponse(
            status_code=404,
            content=format_scim_error(404, "User not found"),
            media_type=SCIM_CONTENT_TYPE,
        )

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        return JSONResponse(
            status_code=404,
            content=format_scim_error(404, "User not found"),
            media_type=SCIM_CONTENT_TYPE,
        )

    base_url = str(request.base_url).rstrip("/") + "/api/v1/scim"
    return JSONResponse(
        content=format_scim_user(user, base_url),
        media_type=SCIM_CONTENT_TYPE,
    )


@router.put("/Users/{user_id}")
async def update_user(
    user_id: str,
    request: Request,
    scim_token: ScimToken = Depends(_verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = _uuid.UUID(user_id)
    except ValueError:
        return JSONResponse(
            status_code=404,
            content=format_scim_error(404, "User not found"),
            media_type=SCIM_CONTENT_TYPE,
        )

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        return JSONResponse(
            status_code=404,
            content=format_scim_error(404, "User not found"),
            media_type=SCIM_CONTENT_TYPE,
        )

    body = await request.json()
    parsed = parse_scim_user(body)

    if parsed["email"] and parsed["email"] != user.email:
        user.email = parsed["email"]
    if parsed["name"]:
        user.name = parsed["name"]

    if not parsed["active"] and user.auth_provider != "deactivated":
        user.password_hash = None
        user.auth_provider = "deactivated"

    await db.commit()
    await audit(
        None,
        "scim.user.update",
        resource_type="user",
        resource_id=str(user.id),
        detail=f"SCIM updated: {user.email}",
    )

    base_url = str(request.base_url).rstrip("/") + "/api/v1/scim"
    return JSONResponse(
        content=format_scim_user(user, base_url),
        media_type=SCIM_CONTENT_TYPE,
    )


@router.delete("/Users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    scim_token: ScimToken = Depends(_verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = _uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    email = user.email
    user_id_str = str(user.id)
    await db.delete(user)
    await db.commit()

    await bus.emit(UserDeleted(user_id=user_id_str, email=email))
    await audit(
        None,
        "scim.user.delete",
        resource_type="user",
        resource_id=user_id_str,
        detail=f"SCIM deprovisioned: {email}",
    )
