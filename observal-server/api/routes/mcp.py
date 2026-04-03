import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from models.mcp import ListingStatus, McpCustomField, McpDownload, McpListing
from models.user import User
from schemas.mcp import (
    McpAnalyzeRequest,
    McpAnalyzeResponse,
    McpInstallRequest,
    McpInstallResponse,
    McpListingResponse,
    McpListingSummary,
    McpSubmitRequest,
)
from services.config_generator import generate_config
from services.mcp_validator import analyze_repo, run_validation

router = APIRouter(prefix="/api/v1/mcps", tags=["mcp"])


@router.post("/analyze", response_model=McpAnalyzeResponse)
async def analyze_mcp(
    req: McpAnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    result = await analyze_repo(req.git_url)
    return McpAnalyzeResponse(**result)


@router.post("/submit", response_model=McpListingResponse)
async def submit_mcp(
    req: McpSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    listing = McpListing(
        name=req.name,
        version=req.version,
        git_url=req.git_url,
        description=req.description,
        category=req.category,
        owner=req.owner,
        supported_ides=req.supported_ides,
        setup_instructions=req.setup_instructions,
        changelog=req.changelog,
        status=ListingStatus.pending,
        submitted_by=current_user.id,
    )
    db.add(listing)
    await db.flush()

    for fname, fval in req.custom_fields.items():
        db.add(McpCustomField(listing_id=listing.id, field_name=fname, field_value=fval))

    await db.commit()
    await db.refresh(listing)

    try:
        await run_validation(listing, db)
    except Exception:
        pass

    return McpListingResponse.model_validate(listing)


@router.get("", response_model=list[McpListingSummary])
async def list_mcps(
    category: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(McpListing).where(McpListing.status == ListingStatus.approved)
    if category:
        stmt = stmt.where(McpListing.category == category)
    if search:
        stmt = stmt.where(McpListing.name.ilike(f"%{search}%") | McpListing.description.ilike(f"%{search}%"))
    result = await db.execute(stmt.order_by(McpListing.created_at.desc()))
    return [McpListingSummary.model_validate(r) for r in result.scalars().all()]


@router.get("/{listing_id}", response_model=McpListingResponse)
async def get_mcp(listing_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpListing).where(McpListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return McpListingResponse.model_validate(listing)


@router.post("/{listing_id}/install", response_model=McpInstallResponse)
async def install_mcp(
    listing_id: uuid.UUID,
    req: McpInstallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(McpListing).where(McpListing.id == listing_id, McpListing.status == ListingStatus.approved)
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Approved listing not found")

    db.add(McpDownload(listing_id=listing.id, user_id=current_user.id, ide=req.ide))
    await db.commit()

    snippet = generate_config(listing, req.ide)
    return McpInstallResponse(listing_id=listing.id, ide=req.ide, config_snippet=snippet)


@router.delete("/{listing_id}")
async def delete_mcp(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from models.feedback import Feedback

    result = await db.execute(select(McpListing).where(McpListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.submitted_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    # Delete related records with correct type filter
    for r in (
        (await db.execute(select(Feedback).where(Feedback.listing_id == listing_id, Feedback.listing_type == "mcp")))
        .scalars()
        .all()
    ):
        await db.delete(r)
    for r in (await db.execute(select(McpDownload).where(McpDownload.listing_id == listing_id))).scalars().all():
        await db.delete(r)

    await db.delete(listing)
    await db.commit()
    return {"deleted": str(listing_id)}
