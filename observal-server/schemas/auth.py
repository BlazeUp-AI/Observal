import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, model_validator

from models.user import UserRole


class InitRequest(BaseModel):
    email: EmailStr
    name: str
    password: str | None = None


class LoginRequest(BaseModel):
    api_key: str | None = None
    email: EmailStr | None = None
    password: str | None = None

    @model_validator(mode="after")
    def _require_credentials(self):
        has_key = bool(self.api_key)
        has_password = bool(self.email and self.password)
        if not has_key and not has_password:
            raise ValueError("Provide api_key or email+password")
        return self


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


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


class CodeExchangeRequest(BaseModel):
    code: str


class RequestResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str
    new_password: str


class TokenRequest(BaseModel):
    api_key: str | None = None
    email: EmailStr | None = None
    password: str | None = None

    @model_validator(mode="after")
    def _require_credentials(self):
        has_key = bool(self.api_key)
        has_password = bool(self.email and self.password)
        if not has_key and not has_password:
            raise ValueError("Provide api_key or email+password")
        return self


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class RevokeRequest(BaseModel):
    refresh_token: str
