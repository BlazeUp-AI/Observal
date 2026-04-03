import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_current_user, get_db
from models.agent import Agent, AgentDownload, AgentGoalSection, AgentGoalTemplate, AgentMcpLink, AgentStatus
from models.mcp import ListingStatus, McpListing
from models.user import User
from schemas.agent import (
    AgentCreateRequest,
    AgentInstallRequest,
    AgentInstallResponse,
    AgentResponse,
    AgentSummary,
    AgentUpdateRequest,
    GoalSectionResponse,
    GoalTemplateResponse,
    McpLinkResponse,
)
from services.agent_config_generator import generate_agent_config

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Eager-load options for Agent queries to avoid MissingGreenlet in async
_agent_load_options = [
    selectinload(Agent.mcp_links).selectinload(AgentMcpLink.mcp_listing),
    selectinload(Agent.goal_template).selectinload(AgentGoalTemplate.sections),
]


async def _load_agent(db: AsyncSession, *where_clauses) -> Agent | None:
    stmt = select(Agent).where(*where_clauses).options(*_agent_load_options)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _agent_to_response(agent: Agent) -> AgentResponse:
    mcp_links = [
        McpLinkResponse(
            mcp_listing_id=link.mcp_listing_id,
            mcp_name=link.mcp_listing.name if link.mcp_listing else "(deleted)",
            order=link.order,
        )
        for link in agent.mcp_links
    ]
    goal_template = None
    if agent.goal_template:
        sections = [
            GoalSectionResponse(
                name=s.name, description=s.description, grounding_required=s.grounding_required, order=s.order
            )
            for s in agent.goal_template.sections
        ]
        goal_template = GoalTemplateResponse(description=agent.goal_template.description, sections=sections)

    agent_dict = {c.key: getattr(agent, c.key) for c in Agent.__table__.columns}
    agent_dict["mcp_links"] = mcp_links
    agent_dict["goal_template"] = goal_template
    return AgentResponse(**agent_dict)


async def _validate_mcp_ids(mcp_ids: list[uuid.UUID], db: AsyncSession) -> list[McpListing]:
    listings = []
    for mid in mcp_ids:
        result = await db.execute(
            select(McpListing).where(McpListing.id == mid, McpListing.status == ListingStatus.approved)
        )
        listing = result.scalar_one_or_none()
        if not listing:
            raise HTTPException(status_code=400, detail=f"MCP server {mid} not found or not approved")
        listings.append(listing)
    return listings


@router.post("", response_model=AgentResponse)
async def create_agent(
    req: AgentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _validate_mcp_ids(req.mcp_server_ids, db)

    agent = Agent(
        name=req.name,
        version=req.version,
        description=req.description,
        owner=req.owner,
        prompt=req.prompt,
        model_name=req.model_name,
        model_config_json=req.model_config_json,
        external_mcps=[m.model_dump() for m in req.external_mcps],
        supported_ides=req.supported_ides,
        created_by=current_user.id,
    )
    db.add(agent)
    await db.flush()

    for i, mid in enumerate(req.mcp_server_ids):
        db.add(AgentMcpLink(agent_id=agent.id, mcp_listing_id=mid, order=i))

    goal = AgentGoalTemplate(agent_id=agent.id, description=req.goal_template.description)
    db.add(goal)
    await db.flush()

    for i, sec in enumerate(req.goal_template.sections):
        db.add(
            AgentGoalSection(
                goal_template_id=goal.id,
                name=sec.name,
                description=sec.description,
                grounding_required=sec.grounding_required,
                order=i,
            )
        )

    await db.commit()
    agent = await _load_agent(db, Agent.id == agent.id)
    return _agent_to_response(agent)


@router.get("", response_model=list[AgentSummary])
async def list_agents(
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Agent).where(Agent.status == AgentStatus.active)
    if search:
        stmt = stmt.where(Agent.name.ilike(f"%{search}%") | Agent.description.ilike(f"%{search}%"))
    result = await db.execute(stmt.order_by(Agent.created_at.desc()))
    return [AgentSummary.model_validate(a) for a in result.scalars().all()]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    agent = await _load_agent(db, Agent.id == agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_to_response(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    req: AgentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = await _load_agent(db, Agent.id == agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not the agent owner")

    for field in (
        "name",
        "version",
        "description",
        "owner",
        "prompt",
        "model_name",
        "model_config_json",
        "supported_ides",
    ):
        val = getattr(req, field)
        if val is not None:
            setattr(agent, field, val)

    if req.external_mcps is not None:
        agent.external_mcps = [m.model_dump() for m in req.external_mcps]

    if req.mcp_server_ids is not None:
        await _validate_mcp_ids(req.mcp_server_ids, db)
        old_links = (await db.execute(select(AgentMcpLink).where(AgentMcpLink.agent_id == agent_id))).scalars().all()
        for link in old_links:
            await db.delete(link)
        for i, mid in enumerate(req.mcp_server_ids):
            db.add(AgentMcpLink(agent_id=agent.id, mcp_listing_id=mid, order=i))

    if req.goal_template is not None:
        if agent.goal_template:
            old_sections = (
                (
                    await db.execute(
                        select(AgentGoalSection).where(AgentGoalSection.goal_template_id == agent.goal_template.id)
                    )
                )
                .scalars()
                .all()
            )
            for sec in old_sections:
                await db.delete(sec)
            await db.delete(agent.goal_template)
            await db.flush()
        goal = AgentGoalTemplate(agent_id=agent.id, description=req.goal_template.description)
        db.add(goal)
        await db.flush()
        for i, sec in enumerate(req.goal_template.sections):
            db.add(
                AgentGoalSection(
                    goal_template_id=goal.id,
                    name=sec.name,
                    description=sec.description,
                    grounding_required=sec.grounding_required,
                    order=i,
                )
            )

    await db.commit()
    agent = await _load_agent(db, Agent.id == agent_id)
    return _agent_to_response(agent)


@router.post("/{agent_id}/install", response_model=AgentInstallResponse)
async def install_agent(
    agent_id: uuid.UUID,
    req: AgentInstallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = await _load_agent(db, Agent.id == agent_id, Agent.status == AgentStatus.active)
    if not agent:
        raise HTTPException(status_code=404, detail="Active agent not found")

    snippet = generate_agent_config(agent, req.ide)
    db.add(AgentDownload(agent_id=agent.id, user_id=current_user.id, ide=req.ide))
    await db.commit()

    return AgentInstallResponse(agent_id=agent.id, ide=req.ide, config_snippet=snippet)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from models.eval import EvalRun, Scorecard
    from models.feedback import Feedback

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    # Delete related records with correct type filters
    for r in (
        (await db.execute(select(Feedback).where(Feedback.listing_id == agent_id, Feedback.listing_type == "agent")))
        .scalars()
        .all()
    ):
        await db.delete(r)
    for r in (await db.execute(select(Scorecard).where(Scorecard.agent_id == agent_id))).scalars().all():
        await db.delete(r)
    for r in (await db.execute(select(EvalRun).where(EvalRun.agent_id == agent_id))).scalars().all():
        await db.delete(r)
    for r in (await db.execute(select(AgentDownload).where(AgentDownload.agent_id == agent_id))).scalars().all():
        await db.delete(r)
    # AgentMcpLink, AgentGoalTemplate, AgentGoalSection handled by cascade="all, delete-orphan"

    await db.delete(agent)
    await db.commit()
    return {"deleted": str(agent_id)}
