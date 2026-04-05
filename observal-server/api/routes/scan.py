"""Bulk scan endpoint: register multiple items in one call."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from models.mcp import ListingStatus, McpListing
from models.user import User

router = APIRouter(prefix="/api/v1/scan", tags=["scan"])


class ScannedMcp(BaseModel):
    name: str
    command: str | None = None
    args: list[str] = []
    url: str | None = None
    env: dict[str, str] = {}


class ScanRequest(BaseModel):
    ide: str
    mcps: list[ScannedMcp] = []


class RegisteredItem(BaseModel):
    name: str
    id: str
    status: str  # "created" or "existing"


class ScanResponse(BaseModel):
    registered: list[RegisteredItem] = []


@router.post("", response_model=ScanResponse)
async def bulk_scan(
    req: ScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    registered = []
    for mcp in req.mcps:
        # Check if already registered by name
        result = await db.execute(select(McpListing).where(McpListing.name == mcp.name))
        existing = result.scalar_one_or_none()
        if existing:
            registered.append(RegisteredItem(name=mcp.name, id=str(existing.id), status="existing"))
            continue

        # Auto-register as pending (owner can install their own pending items)
        listing = McpListing(
            name=mcp.name,
            version="0.1.0",
            git_url=mcp.url or "",
            description=f"Auto-registered from {req.ide} config",
            category="scanned",
            owner=current_user.username if hasattr(current_user, "username") else str(current_user.id),
            supported_ides=[req.ide],
            status=ListingStatus.pending,
            submitted_by=current_user.id,
        )
        db.add(listing)
        await db.flush()
        registered.append(RegisteredItem(name=mcp.name, id=str(listing.id), status="created"))

    await db.commit()
    return ScanResponse(registered=registered)
