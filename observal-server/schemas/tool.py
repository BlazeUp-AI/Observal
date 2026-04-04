import uuid
from datetime import datetime

from pydantic import BaseModel

from models.mcp import ListingStatus


class ToolSubmitRequest(BaseModel):
    name: str
    version: str
    description: str
    owner: str
    category: str
    function_schema: dict = {}
    auth_type: str = "none"
    auth_config: dict | None = None
    endpoint_url: str | None = None
    rate_limit: dict | None = None
    supported_ides: list[str] = []


class ToolListingResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    owner: str
    category: str
    function_schema: dict
    auth_type: str
    endpoint_url: str | None
    supported_ides: list[str]
    status: ListingStatus
    rejection_reason: str | None = None
    submitted_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ToolListingSummary(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    category: str
    owner: str
    supported_ides: list[str]
    status: ListingStatus
    model_config = {"from_attributes": True}


class ToolInstallRequest(BaseModel):
    ide: str


class ToolInstallResponse(BaseModel):
    listing_id: uuid.UUID
    ide: str
    config_snippet: dict
