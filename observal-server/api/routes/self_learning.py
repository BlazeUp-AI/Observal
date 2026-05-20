# SPDX-FileCopyrightText: 2026 Shaan Narendran <shaannaren06@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Self-learning endpoints (open-source edition).

When self-learning is enabled for an agent, the system can synthesize
behavioral suggestions from the latest insight report and propose them
as a new agent version. That version enters the review queue — an admin
must approve it before users receive the updated rules.

Flow:
1. Owner toggles self_learning_enabled on the agent
2. Owner or automation calls POST /{agent_id}/self-learning/propose
3. System fetches latest completed insight report, synthesizes suggestions
4. A new AgentVersion (patch bump) is created with suggestions appended to the prompt
5. Version enters the review queue (status=pending)
6. Admin approves → version becomes latest → users get updated rules on next pull
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_role
from models.agent import Agent, AgentStatus, AgentVersion
from models.insight_report import InsightReport, InsightReportStatus
from models.user import User, UserRole
from services.versioning import bump_version

router = APIRouter(prefix="/api/v1/agents", tags=["self-learning"])


class SelfLearningToggleRequest(BaseModel):
    enabled: bool


class SelfLearningToggleResponse(BaseModel):
    enabled: bool
    message: str


class ProposeResponse(BaseModel):
    version_id: str
    version: str
    status: str
    message: str


async def _resolve_agent(agent_id: str, db: AsyncSession) -> Agent:
    import uuid as _uuid

    try:
        uid = _uuid.UUID(agent_id)
        stmt = select(Agent).where(Agent.id == uid)
    except ValueError:
        stmt = select(Agent).where(Agent.name == agent_id)

    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}/self-learning", response_model=SelfLearningToggleResponse)
async def toggle_self_learning(
    agent_id: str,
    body: SelfLearningToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    """Enable or disable self-learning for an agent."""
    agent = await _resolve_agent(agent_id, db)

    if agent.created_by != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only the agent owner or admin can toggle self-learning")

    agent.self_learning_enabled = body.enabled
    await db.commit()

    msg = (
        "Self-learning enabled. Use POST /self-learning/propose to create a version from insights."
        if body.enabled
        else "Self-learning disabled."
    )
    return SelfLearningToggleResponse(enabled=agent.self_learning_enabled, message=msg)


@router.get("/{agent_id}/self-learning")
async def get_self_learning_status(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    """Get self-learning status for an agent."""
    agent = await _resolve_agent(agent_id, db)
    return {"enabled": agent.self_learning_enabled}


@router.post("/{agent_id}/self-learning/propose", response_model=ProposeResponse)
async def propose_self_learning_version(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    """Synthesize suggestions from the latest insight report and create a new agent version.

    The new version enters the review queue (status=pending). An admin must
    approve it before users receive the updated rules on their next pull.
    """
    agent = await _resolve_agent(agent_id, db)

    if agent.created_by != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only the agent owner or admin can propose self-learning versions")

    if not agent.self_learning_enabled:
        raise HTTPException(status_code=400, detail="Self-learning is not enabled for this agent")

    # Must have a current version to base the new one on
    current_version = agent.latest_version
    if not current_version:
        raise HTTPException(status_code=400, detail="Agent has no published version to base the proposal on")

    # Fetch the latest completed insight report
    insight_stmt = (
        select(InsightReport)
        .where(
            InsightReport.agent_id == agent.id,
            InsightReport.status == InsightReportStatus.completed,
        )
        .order_by(InsightReport.completed_at.desc())
        .limit(1)
    )
    insight_result = await db.execute(insight_stmt)
    latest_report = insight_result.scalar_one_or_none()

    if not latest_report:
        raise HTTPException(status_code=404, detail="No completed insight report found. Generate one first.")

    # Synthesize suggestions
    from ee.observal_insights.skill_synthesis import synthesize_from_insight_report

    report_content = {
        "narrative": latest_report.narrative or {},
        "facets_summary": (latest_report.aggregated_data or {}).get("facets_summary", {}),
        "regressions": (latest_report.aggregated_data or {}).get("regressions", []),
        "sessions_analyzed": latest_report.sessions_analyzed or 0,
    }
    suggestions_md = synthesize_from_insight_report(report_content)

    if not suggestions_md:
        raise HTTPException(
            status_code=422,
            detail="Nothing actionable in the latest insight report — no version proposed.",
        )

    # Build the new prompt: current prompt + suggestions section
    base_prompt = current_version.prompt or ""
    # Remove any previously injected suggestions block (idempotent re-proposals)
    marker = "## Learned from Production"
    if marker in base_prompt:
        base_prompt = base_prompt[: base_prompt.index(marker)].rstrip()

    new_prompt = f"{base_prompt}\n\n{suggestions_md}" if base_prompt else suggestions_md

    # Bump version (patch)
    new_version_str = bump_version(current_version.version, "patch")

    # Check for duplicate version
    dup_stmt = select(AgentVersion).where(
        AgentVersion.agent_id == agent.id,
        AgentVersion.version == new_version_str,
    )
    if (await db.execute(dup_stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Version {new_version_str!r} already exists. Approve or reject it before proposing again.",
        )

    # Create the new version — enters review queue
    now = datetime.now(UTC)
    new_ver = AgentVersion(
        agent_id=agent.id,
        version=new_version_str,
        description=f"Self-learning: suggestions from insight report ({latest_report.sessions_analyzed} sessions analyzed)",
        prompt=new_prompt,
        model_name=current_version.model_name,
        model_config_json=current_version.model_config_json,
        models_by_ide=current_version.models_by_ide,
        external_mcps=current_version.external_mcps,
        supported_ides=current_version.supported_ides,
        required_ide_features=current_version.required_ide_features,
        inferred_supported_ides=current_version.inferred_supported_ides,
        status=AgentStatus.pending,
        released_by=current_user.id,
        released_at=now,
    )
    db.add(new_ver)
    await db.flush()

    # Copy components from the current version
    from models.agent_component import AgentComponent

    for comp in current_version.components:
        db.add(
            AgentComponent(
                agent_version_id=new_ver.id,
                component_type=comp.component_type,
                component_id=comp.component_id,
                component_name=comp.component_name,
                resolved_version=comp.resolved_version,
                order_index=comp.order_index,
                config_override=comp.config_override,
            )
        )

    await db.commit()

    from services.audit_helpers import audit

    await audit(
        current_user,
        "agent.self_learning.propose",
        resource_type="agent",
        resource_id=str(agent.id),
        resource_name=agent.name,
        detail=new_version_str,
    )

    return ProposeResponse(
        version_id=str(new_ver.id),
        version=new_version_str,
        status="pending",
        message=f"Version {new_version_str} created with self-learning suggestions and submitted for review.",
    )
