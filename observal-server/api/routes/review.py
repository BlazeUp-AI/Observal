import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_db, require_role, resolve_prefix_id
from models.agent import Agent, AgentStatus
from models.component_bundle import ComponentBundle
from models.hook import HookListing
from models.mcp import ListingStatus, McpListing
from models.prompt import PromptListing
from models.sandbox import SandboxListing
from models.skill import SkillListing
from models.user import User, UserRole
from schemas.mcp import ReviewActionRequest

router = APIRouter(prefix="/api/v1/review", tags=["review"])

LISTING_MODELS = {
    "mcp": McpListing,
    "skill": SkillListing,
    "hook": HookListing,
    "prompt": PromptListing,
    "sandbox": SandboxListing,
}


async def _find_listing(listing_id: str, db: AsyncSession):
    """Find a listing by ID, prefix, or name across all component types."""
    hits = []
    for listing_type, model in LISTING_MODELS.items():
        try:
            listing = await resolve_prefix_id(model, listing_id, db)
            hits.append((listing_type, listing))
        except HTTPException as e:
            if e.status_code == 400:
                raise e
            continue

    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        types = [h[0] for h in hits]
        raise HTTPException(
            status_code=400,
            detail=f"Prefix '{listing_id}' matches records across multiple types: {', '.join(types)}",
        )

    # Fallback: name-based lookup
    for listing_type, model in LISTING_MODELS.items():
        result = await db.execute(select(model).where(model.name == listing_id))
        listing = result.scalar_one_or_none()
        if listing:
            return listing_type, listing

    return None, None


async def _check_agent_components_ready(agent: Agent, db: AsyncSession) -> tuple[bool, list[dict]]:
    """Check if all of an agent's components are approved."""
    if not agent.components:
        return True, []

    by_type: dict[str, list[uuid.UUID]] = {}
    for comp in agent.components:
        by_type.setdefault(comp.component_type, []).append(comp.component_id)

    blocking: list[dict] = []
    for comp_type, ids in by_type.items():
        model = LISTING_MODELS.get(comp_type)
        if not model:
            continue
        rows = (await db.execute(select(model.id, model.name, model.status).where(model.id.in_(ids)))).all()
        for row in rows:
            if row.status != ListingStatus.approved:
                blocking.append(
                    {
                        "component_type": comp_type,
                        "component_id": str(row.id),
                        "name": row.name,
                        "status": row.status.value,
                    }
                )
    return len(blocking) == 0, blocking


@router.get("")
async def list_pending(
    type: str | None = Query(None),
    tab: str | None = Query(None, description="'agents' to list pending agents, default lists components"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    if tab == "agents":
        result = await db.execute(
            select(Agent)
            .where(Agent.status == AgentStatus.pending)
            .options(selectinload(Agent.components))
            .order_by(Agent.created_at.desc())
        )
        agents = result.scalars().all()

        user_ids = {a.created_by for a in agents}
        user_map: dict[uuid.UUID, str] = {}
        if user_ids:
            rows = await db.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
            user_map = {r[0]: r[1] for r in rows.all()}

        items = []
        for a in agents:
            components_ready, blocking = await _check_agent_components_ready(a, db)
            items.append(
                {
                    "type": "agent",
                    "id": str(a.id),
                    "name": a.name,
                    "description": a.description or "",
                    "version": a.version or "",
                    "owner": a.owner or "",
                    "status": a.status.value,
                    "submitted_by": user_map.get(a.created_by, str(a.created_by)),
                    "created_at": a.created_at.isoformat() if a.created_at else "",
                    "component_count": len(a.components),
                    "components_ready": components_ready,
                    "blocking_components": blocking,
                }
            )
        return items

    models_to_query = {type: LISTING_MODELS[type]} if type and type in LISTING_MODELS else LISTING_MODELS
    items = []
    user_ids: set[uuid.UUID] = set()
    for listing_type, model in models_to_query.items():
        result = await db.execute(
            select(model).where(model.status == ListingStatus.pending).order_by(model.created_at.desc())
        )
        for r in result.scalars().all():
            user_ids.add(r.submitted_by)
            item: dict = {
                "type": listing_type,
                "id": str(r.id),
                "name": r.name,
                "description": getattr(r, "description", None) or "",
                "version": getattr(r, "version", None) or "",
                "owner": getattr(r, "owner", None) or "",
                "status": r.status.value,
                "submitted_by": r.submitted_by,
                "created_at": r.created_at.isoformat(),
                "bundle_id": str(r.bundle_id) if isinstance(getattr(r, "bundle_id", None), uuid.UUID) else None,
            }
            # Include validation results for MCP listings
            if listing_type == "mcp" and hasattr(r, "validation_results"):
                item["mcp_validated"] = getattr(r, "mcp_validated", False)
                item["validation_results"] = [
                    {
                        "stage": vr.stage,
                        "passed": vr.passed,
                        "details": vr.details,
                    }
                    for vr in r.validation_results
                ]
            items.append(item)

    # Resolve bundle names
    bundle_ids = {i["bundle_id"] for i in items if i.get("bundle_id")}
    bundle_map: dict[str, str] = {}
    if bundle_ids:
        brows = await db.execute(
            select(ComponentBundle.id, ComponentBundle.name).where(
                ComponentBundle.id.in_([uuid.UUID(b) for b in bundle_ids])
            )
        )
        bundle_map = {str(r[0]): r[1] for r in brows.all()}
    for item in items:
        if item.get("bundle_id"):
            item["bundle_name"] = bundle_map.get(item["bundle_id"], "")

    # Resolve user UUIDs to display names
    user_map: dict[uuid.UUID, str] = {}
    if user_ids:
        result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in result.scalars().all():
            user_map[u.id] = u.name or u.email

    for item in items:
        uid = item["submitted_by"]
        item["submitted_by"] = user_map.get(uid, str(uid))

    return items


@router.get("/{listing_id}")
async def get_review(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    listing_type, listing = await _find_listing(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    result = {
        "type": listing_type,
        "id": str(listing.id),
        "name": listing.name,
        "description": getattr(listing, "description", None) or "",
        "version": getattr(listing, "version", None) or "",
        "owner": getattr(listing, "owner", None) or "",
        "status": listing.status.value,
        "submitted_by": str(listing.submitted_by),
        "created_at": listing.created_at.isoformat(),
    }
    if listing_type == "mcp" and hasattr(listing, "validation_results"):
        result["mcp_validated"] = getattr(listing, "mcp_validated", False)
        result["validation_results"] = [
            {"stage": vr.stage, "passed": vr.passed, "details": vr.details} for vr in listing.validation_results
        ]
    return result


@router.post("/{listing_id}/approve")
async def approve(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    listing_type, listing = await _find_listing(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    listing.status = ListingStatus.approved
    await db.commit()
    await db.refresh(listing)
    return {"type": listing_type, "id": str(listing.id), "name": listing.name, "status": listing.status.value}


@router.post("/{listing_id}/reject")
async def reject(
    listing_id: str,
    req: ReviewActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    listing_type, listing = await _find_listing(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    listing.status = ListingStatus.rejected
    listing.rejection_reason = req.reason
    await db.commit()
    await db.refresh(listing)
    return {"type": listing_type, "id": str(listing.id), "name": listing.name, "status": listing.status.value}


# ---------------------------------------------------------------------------
# Agent review
# ---------------------------------------------------------------------------


class AgentRejectRequest(BaseModel):
    reason: str


@router.post("/agents/{agent_id}/approve")
async def approve_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    agent = (
        await db.execute(select(Agent).where(Agent.id == agent_id).options(selectinload(Agent.components)))
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != AgentStatus.pending:
        raise HTTPException(status_code=400, detail=f"Agent is '{agent.status.value}', not pending")

    components_ready, blocking = await _check_agent_components_ready(agent, db)
    if not components_ready:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Cannot approve: some components are not approved yet",
                "blocking_components": blocking,
            },
        )

    agent.status = AgentStatus.active
    agent.rejection_reason = None
    await db.commit()
    return {"id": str(agent.id), "name": agent.name, "status": agent.status.value}


@router.post("/agents/{agent_id}/reject")
async def reject_agent(
    agent_id: uuid.UUID,
    req: AgentRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status not in (AgentStatus.pending, AgentStatus.active):
        raise HTTPException(status_code=400, detail=f"Agent is '{agent.status.value}', cannot reject")

    agent.status = AgentStatus.rejected
    agent.rejection_reason = req.reason
    await db.commit()
    return {"id": str(agent.id), "name": agent.name, "status": agent.status.value}


# ---------------------------------------------------------------------------
# Bundle review (atomic approve/reject)
# ---------------------------------------------------------------------------


@router.post("/bundles/{bundle_id}/approve")
async def approve_bundle(
    bundle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    bundle = (await db.execute(select(ComponentBundle).where(ComponentBundle.id == bundle_id))).scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    count = 0
    for model in LISTING_MODELS.values():
        result = await db.execute(select(model).where(model.bundle_id == bundle_id))
        for listing in result.scalars().all():
            listing.status = ListingStatus.approved
            count += 1

    await db.commit()
    return {"bundle_id": str(bundle_id), "name": bundle.name, "approved_count": count}


@router.post("/bundles/{bundle_id}/reject")
async def reject_bundle(
    bundle_id: uuid.UUID,
    req: ReviewActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    bundle = (await db.execute(select(ComponentBundle).where(ComponentBundle.id == bundle_id))).scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    count = 0
    for model in LISTING_MODELS.values():
        result = await db.execute(select(model).where(model.bundle_id == bundle_id))
        for listing in result.scalars().all():
            listing.status = ListingStatus.rejected
            listing.rejection_reason = req.reason
            count += 1

    await db.commit()
    return {"bundle_id": str(bundle_id), "name": bundle.name, "rejected_count": count}
