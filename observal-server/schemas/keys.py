"""Pydantic schemas for API key management endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from models.api_key import ApiKeyEnvironment


class KeyCreateRequest(BaseModel):
    """Request schema for creating a new API key."""

    name: str = Field(..., min_length=1, max_length=100, description="User-friendly name for the key")
    environment: ApiKeyEnvironment = Field(..., description="Environment: live, test, or dev")
    expires_in_days: int | None = Field(None, ge=1, description="Days until expiration (null = never expires)")


class KeyCreateResponse(BaseModel):
    """Response schema for create key endpoint. Key is shown only once."""

    key: str = Field(..., description="Full API key - SAVE THIS! Shown only once")
    id: UUID
    name: str
    prefix: str = Field(..., description="First 10 chars for display")
    environment: ApiKeyEnvironment
    created_at: datetime
    expires_at: datetime | None


class KeyResponse(BaseModel):
    """Schema for API key metadata (without the actual key)."""

    id: UUID
    name: str
    prefix: str
    environment: ApiKeyEnvironment
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    last_used_ip: str | None
    revoked_at: datetime | None


class KeyListResponse(BaseModel):
    """Response schema for list keys endpoint with pagination."""

    keys: list[KeyResponse]
    total: int = Field(..., description="Total number of keys matching filters")
    limit: int
    offset: int


class KeyRotateRequest(BaseModel):
    """Request schema for rotating an API key."""

    grace_period_hours: int | None = Field(24, ge=1, le=168, description="Hours until old key expires")
    immediate: bool = Field(False, description="If true, old key revoked immediately")


class KeyRotateResponse(BaseModel):
    """Response schema for rotate key endpoint."""

    new_key: str = Field(..., description="New API key - SAVE THIS! Shown only once")
    new_key_id: UUID
    old_key_id: UUID
    old_key_expires_at: datetime = Field(..., description="When the old key stops working")
    grace_period_hours: int
