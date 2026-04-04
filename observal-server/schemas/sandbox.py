import uuid
from datetime import datetime

from pydantic import BaseModel

from models.mcp import ListingStatus


class SandboxSubmitRequest(BaseModel):
    name: str
    version: str
    description: str
    owner: str
    runtime_type: str
    image: str
    dockerfile_url: str | None = None
    resource_limits: dict = {}
    network_policy: str = "none"
    allowed_mounts: list[str] = []
    env_vars: dict = {}
    entrypoint: str | None = None
    supported_ides: list[str] = []


class SandboxListingResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    owner: str
    runtime_type: str
    image: str
    resource_limits: dict
    network_policy: str
    supported_ides: list[str]
    status: ListingStatus
    rejection_reason: str | None = None
    submitted_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class SandboxListingSummary(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    runtime_type: str
    owner: str
    supported_ides: list[str]
    status: ListingStatus
    model_config = {"from_attributes": True}


class SandboxInstallRequest(BaseModel):
    ide: str


class SandboxInstallResponse(BaseModel):
    listing_id: uuid.UUID
    ide: str
    config_snippet: dict
