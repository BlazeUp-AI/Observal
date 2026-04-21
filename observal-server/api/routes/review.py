import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import cast, or_, select, String
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


async def _query_pending_agents(db: AsyncSession) -> list[dict]:
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


async def _query_pending_components(db: AsyncSession, type_filter: str | None = None) -> list[dict]:
    models_to_query = (
        {type_filter: LISTING_MODELS[type_filter]} if type_filter and type_filter in LISTING_MODELS else LISTING_MODELS
    )
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
                        "run_at": vr.run_at.isoformat() if vr.run_at else None,
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


@router.get("")
async def list_pending(
    type: str | None = Query(None),
    tab: str | None = Query(
        None,
        description="Filter by type: 'agents' or 'components'. Defaults to all pending items.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    if tab == "agents":
        return await _query_pending_agents(db)

    if tab == "components":
        return await _query_pending_components(db, type)

    # Default: return both agents and components
    agents = await _query_pending_agents(db)
    components = await _query_pending_components(db, type)

    # Merge and sort by created_at (most recent first)
    all_items = agents + components
    all_items.sort(key=lambda x: x["created_at"], reverse=True)

    return all_items


_DETAIL_FIELDS: dict[str, list[str]] = {
    "mcp": [
        "git_url", "git_ref", "category", "transport", "framework", "docker_image",
        "command", "args", "url", "headers", "auto_approve", "tools_schema",
        "environment_variables", "supported_ides", "setup_instructions", "changelog",
        "rejection_reason", "bundle_id",
    ],
    "skill": [
        "git_url", "git_ref", "skill_path", "target_agents", "task_type", "triggers",
        "slash_command", "has_scripts", "has_templates", "is_power", "power_md",
        "mcp_server_config", "activation_keywords", "supported_ides",
        "rejection_reason", "bundle_id",
    ],
    "hook": [
        "git_url", "git_ref", "event", "execution_mode", "priority", "handler_type",
        "handler_config", "input_schema", "output_schema", "scope", "tool_filter",
        "file_pattern", "supported_ides", "rejection_reason", "bundle_id",
    ],
    "prompt": [
        "git_url", "git_ref", "category", "template", "variables", "model_hints",
        "tags", "supported_ides", "rejection_reason", "bundle_id",
    ],
    "sandbox": [
        "git_url", "git_ref", "runtime_type", "image", "dockerfile_url",
        "resource_limits", "network_policy", "allowed_mounts", "env_vars",
        "entrypoint", "supported_ides", "rejection_reason", "bundle_id",
    ],
}


def _safe_serialize(val):
    if isinstance(val, uuid.UUID):
        return str(val)
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def _serialize_listing_detail(listing_type: str, listing) -> dict:
    base = {
        "type": listing_type,
        "id": str(listing.id),
        "name": listing.name,
        "description": getattr(listing, "description", None) or "",
        "version": getattr(listing, "version", None) or "",
        "owner": getattr(listing, "owner", None) or "",
        "status": listing.status.value,
        "submitted_by": str(listing.submitted_by),
        "created_at": listing.created_at.isoformat(),
        "updated_at": listing.updated_at.isoformat() if getattr(listing, "updated_at", None) else None,
    }
    for field in _DETAIL_FIELDS.get(listing_type, []):
        val = getattr(listing, field, None)
        base[field] = _safe_serialize(val)
    if listing_type == "mcp" and hasattr(listing, "validation_results"):
        base["mcp_validated"] = getattr(listing, "mcp_validated", False)
        base["validation_results"] = [
            {
                "stage": vr.stage,
                "passed": vr.passed,
                "details": vr.details,
                "run_at": vr.run_at.isoformat() if vr.run_at else None,
            }
            for vr in listing.validation_results
        ]
    return base


@router.get("/{listing_id}")
async def get_review(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    listing_type, listing = await _find_listing(listing_id, db)

    if listing:
        result = _serialize_listing_detail(listing_type, listing)
    else:
        # Fallback: check Agent table
        try:
            agent_uuid = uuid.UUID(listing_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Listing not found")
        agent = (
            await db.execute(
                select(Agent).where(Agent.id == agent_uuid).options(selectinload(Agent.components))
            )
        ).scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=404, detail="Listing not found")
        components_ready, blocking = await _check_agent_components_ready(agent, db)
        result = {
            "type": "agent",
            "id": str(agent.id),
            "name": agent.name,
            "description": agent.description or "",
            "version": agent.version or "",
            "owner": agent.owner or "",
            "status": agent.status.value,
            "submitted_by": str(agent.created_by),
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
            "git_url": agent.git_url,
            "prompt": agent.prompt,
            "model_name": agent.model_name,
            "model_config_json": agent.model_config_json,
            "external_mcps": agent.external_mcps,
            "supported_ides": agent.supported_ides,
            "required_ide_features": agent.required_ide_features,
            "rejection_reason": agent.rejection_reason,
            "component_count": len(agent.components),
            "components_ready": components_ready,
            "component_blockers": blocking,
            "components": [
                {
                    "component_type": c.component_type,
                    "component_id": str(c.component_id),
                }
                for c in agent.components
            ],
        }

    # Resolve submitted_by UUID to display name
    uid_str = result.get("submitted_by", "")
    try:
        uid = uuid.UUID(uid_str)
        user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if user:
            result["submitted_by"] = user.name or user.email
    except (ValueError, AttributeError):
        pass

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


# ---------------------------------------------------------------------------
# Smart bulk approve: MCP + related skills
# ---------------------------------------------------------------------------


@router.get("/{listing_id}/related-skills")
async def get_related_skills(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    listing_type, listing = await _find_listing(listing_id, db)
    if not listing or listing_type != "mcp":
        return {"skills": []}

    mcp_name = listing.name
    mcp_id = str(listing.id)

    stmt = (
        select(SkillListing)
        .where(
            SkillListing.status == ListingStatus.pending,
            SkillListing.mcp_server_config.isnot(None),
            or_(
                cast(SkillListing.mcp_server_config, String).contains(mcp_name),
                cast(SkillListing.mcp_server_config, String).contains(mcp_id),
            ),
        )
        .order_by(SkillListing.created_at.desc())
    )
    skills = (await db.execute(stmt)).scalars().all()

    user_ids = {s.submitted_by for s in skills}
    user_map: dict[uuid.UUID, str] = {}
    if user_ids:
        rows = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in rows.scalars().all():
            user_map[u.id] = u.name or u.email

    return {
        "skills": [
            {
                "id": str(s.id),
                "type": "skill",
                "name": s.name,
                "version": s.version or "",
                "description": s.description or "",
                "task_type": s.task_type,
                "target_agents": s.target_agents or [],
                "mcp_server_config": s.mcp_server_config,
                "status": s.status.value,
                "submitted_by": user_map.get(s.submitted_by, str(s.submitted_by)),
                "created_at": s.created_at.isoformat(),
            }
            for s in skills
        ]
    }


class McpBulkApproveRequest(BaseModel):
    skill_ids: list[str] = []


@router.post("/{listing_id}/approve-with-skills")
async def approve_mcp_with_skills(
    listing_id: str,
    req: McpBulkApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.reviewer)),
):
    listing_type, listing = await _find_listing(listing_id, db)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing_type != "mcp":
        raise HTTPException(status_code=400, detail="Only MCP listings support bulk skill approve")

    listing.status = ListingStatus.approved

    approved_skill_ids: list[str] = []
    for sid in req.skill_ids:
        try:
            skill_uuid = uuid.UUID(sid)
        except ValueError:
            continue
        skill = (
            await db.execute(select(SkillListing).where(SkillListing.id == skill_uuid))
        ).scalar_one_or_none()
        if skill and skill.status == ListingStatus.pending:
            skill.status = ListingStatus.approved
            approved_skill_ids.append(str(skill.id))

    await db.commit()
    await db.refresh(listing)
    return {
        "mcp": {"id": str(listing.id), "name": listing.name, "status": listing.status.value},
        "approved_skills": len(approved_skill_ids),
        "skill_ids": approved_skill_ids,
    }
