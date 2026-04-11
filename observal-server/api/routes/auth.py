import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from config import settings
from models.invite import InviteCode
from models.user import User, UserRole
from schemas.auth import (
    InitRequest,
    InitResponse,
    InviteCreateRequest,
    InviteListResponse,
    InviteRedeemRequest,
    InviteResponse,
    LoginRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/init", response_model=InitResponse)
async def init_admin(req: InitRequest, db: AsyncSession = Depends(get_db)):
    count = await db.scalar(select(func.count()).select_from(User))
    if count and count > 0:
        raise HTTPException(status_code=400, detail="System already initialized")

    api_key = secrets.token_hex(settings.API_KEY_LENGTH)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    user = User(
        email=req.email,
        name=req.name,
        role=UserRole.admin,
        api_key_hash=key_hash,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return InitResponse(user=UserResponse.model_validate(user), api_key=api_key)


@router.post("/bootstrap", response_model=InitResponse)
async def bootstrap(db: AsyncSession = Depends(get_db)):
    """Auto-create admin account on a fresh server. No input needed."""
    count = await db.scalar(select(func.count()).select_from(User))
    if count and count > 0:
        raise HTTPException(status_code=400, detail="System already initialized")

    api_key = secrets.token_hex(settings.API_KEY_LENGTH)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    user = User(
        email="admin@localhost",
        name="admin",
        role=UserRole.admin,
        api_key_hash=key_hash,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return InitResponse(user=UserResponse.model_validate(user), api_key=api_key)


@router.post("/login", response_model=UserResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    key_hash = hashlib.sha256(req.api_key.encode()).hexdigest()
    result = await db.execute(select(User).where(User.api_key_hash == key_hash))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return UserResponse.model_validate(user)


@router.get("/whoami", response_model=UserResponse)
async def whoami(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


# ── Invite Codes ────────────────────────────────────────────


@router.post("/invite", response_model=InviteResponse)
async def create_invite(
    req: InviteCreateRequest = InviteCreateRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin creates an invite code for a new user."""
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    from datetime import timedelta

    invite = InviteCode(
        role=req.role,
        created_by=current_user.id,
        expires_at=datetime.now(UTC) + timedelta(days=req.expires_days),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    return InviteResponse.model_validate(invite)


@router.post("/redeem", response_model=InitResponse)
async def redeem_invite(req: InviteRedeemRequest, db: AsyncSession = Depends(get_db)):
    """Redeem an invite code to create an account and get an API key."""
    code = req.code.strip().upper()

    result = await db.execute(select(InviteCode).where(InviteCode.code == code))
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    if invite.used_by is not None:
        raise HTTPException(status_code=400, detail="Invite code already used")
    if invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Invite code expired")

    # Generate user credentials
    api_key = secrets.token_hex(settings.API_KEY_LENGTH)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    name = req.name or f"user-{code[-4:]}"
    email = req.email or f"{name.lower().replace(' ', '-')}@localhost"

    try:
        role = UserRole(invite.role)
    except ValueError:
        role = UserRole.developer

    user = User(
        email=email,
        name=name,
        role=role,
        api_key_hash=key_hash,
    )
    db.add(user)

    # Mark invite as used
    invite.used_by = user.id
    invite.used_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(user)

    return InitResponse(user=UserResponse.model_validate(user), api_key=api_key)


@router.get("/invites", response_model=list[InviteListResponse])
async def list_invites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin lists all invite codes."""
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(select(InviteCode).order_by(InviteCode.created_at.desc()))
    return [InviteListResponse.model_validate(i) for i in result.scalars().all()]
