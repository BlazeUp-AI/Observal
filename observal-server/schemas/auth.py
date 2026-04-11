import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from models.user import UserRole


class InitRequest(BaseModel):
    email: EmailStr
    name: str


class LoginRequest(BaseModel):
    api_key: str


class InviteRedeemRequest(BaseModel):
    code: str
    name: str | None = None
    email: str | None = None


class InviteCreateRequest(BaseModel):
    role: str = "developer"
    expires_days: int = 7


class InviteResponse(BaseModel):
    code: str
    role: str
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteListResponse(BaseModel):
    code: str
    role: str
    created_at: datetime
    expires_at: datetime
    used_by: uuid.UUID | None = None
    used_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class InitResponse(BaseModel):
    user: UserResponse
    api_key: str
