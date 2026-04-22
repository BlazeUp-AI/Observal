import uuid
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_role
from models.agent import Agent
from models.feedback import Feedback
from models.mcp import McpListing
from models.user import User, UserRole
from schemas.feedback import FeedbackCreateRequest, FeedbackResponse, FeedbackSummary
from services.audit_helpers import audit
from services.clickhouse import insert_scores

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse)
async def create_feedback(
    req: FeedbackCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    # Validate listing exists
    if req.listing_type == "mcp":
        exists = await db.scalar(select(McpListing.id).where(McpListing.id == req.listing_id))
    else:
        exists = await db.scalar(select(Agent.id).where(Agent.id == req.listing_id))
    if not exists:
        raise HTTPException(status_code=404, detail="Listing not found")

    fb = Feedback(
        listing_id=req.listing_id,
        listing_type=req.listing_type,
        user_id=current_user.id,
        rating=req.rating,
        comment=req.comment,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)

    # Dual-write: also insert into ClickHouse scores table
    from datetime import datetime

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    try:
        await insert_scores(
            [
                {
                    "score_id": str(fb.id),
                    "project_id": "default",
                    "mcp_id": str(req.listing_id) if req.listing_type == "mcp" else None,
                    "agent_id": str(req.listing_id) if req.listing_type == "agent" else None,
                    "user_id": str(current_user.id),
                    "name": "user_rating",
                    "source": "api",
                    "data_type": "numeric",
                    "value": float(req.rating),
                    "comment": req.comment,
                    "metadata": {"listing_type": req.listing_type},
                    "timestamp": now,
                }
            ]
        )
    except Exception:
        pass  # Don't fail the request if ClickHouse write fails

    await audit(current_user, "feedback.create", resource_type="feedback", resource_id=str(fb.id), detail=f"Rating={req.rating} for {req.listing_type}/{req.listing_id}")
    return FeedbackResponse.model_validate(fb)


@router.get("/mcp/{listing_id}", response_model=list[FeedbackResponse])
async def get_mcp_feedback(listing_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Feedback)
        .where(Feedback.listing_id == listing_id, Feedback.listing_type == "mcp")
        .order_by(Feedback.created_at.desc())
    )
    return [FeedbackResponse.model_validate(f) for f in result.scalars().all()]


@router.get("/agent/{listing_id}", response_model=list[FeedbackResponse])
async def get_agent_feedback(listing_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Feedback)
        .where(Feedback.listing_id == listing_id, Feedback.listing_type == "agent")
        .order_by(Feedback.created_at.desc())
    )
    return [FeedbackResponse.model_validate(f) for f in result.scalars().all()]


@router.get("/me", response_model=list[FeedbackResponse])
async def my_feedback_received(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    """Feedback received on listings submitted/created by the current user."""
    mcp_ids = list(
        (await db.execute(select(McpListing.id).where(McpListing.submitted_by == current_user.id))).scalars().all()
    )
    agent_ids = list((await db.execute(select(Agent.id).where(Agent.created_by == current_user.id))).scalars().all())

    all_ids = mcp_ids + agent_ids
    if not all_ids:
        return []

    result = await db.execute(
        select(Feedback).where(Feedback.listing_id.in_(all_ids)).order_by(Feedback.created_at.desc())
    )
    feedbacks = result.scalars().all()
    await audit(current_user, "feedback.my_received", resource_type="feedback")
    return [FeedbackResponse.model_validate(f) for f in feedbacks]


@router.get("/summary/{listing_id}", response_model=FeedbackSummary)
async def feedback_summary(listing_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            func.avg(Feedback.rating).label("avg_rating"),
            func.count(Feedback.id).label("total"),
        ).where(Feedback.listing_id == listing_id)
    )
    row = result.one()
    return FeedbackSummary(
        listing_id=listing_id,
        average_rating=round(float(row.avg_rating or 0), 2),
        total_reviews=row.total,
    )
