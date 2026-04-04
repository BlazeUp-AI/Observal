import uuid
from datetime import datetime

from pydantic import BaseModel

from models.mcp import ListingStatus


class HookSubmitRequest(BaseModel):
    name: str
    version: str
    description: str
    owner: str
    event: str
    execution_mode: str = "async"
    priority: int = 100
    handler_type: str
    handler_config: dict = {}
    input_schema: dict | None = None
    output_schema: dict | None = None
    scope: str = "agent"
    tool_filter: list[str] | None = None
    file_pattern: list[str] | None = None
    supported_ides: list[str] = []


class HookListingResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    owner: str
    event: str
    execution_mode: str
    priority: int
    handler_type: str
    handler_config: dict
    scope: str
    supported_ides: list[str]
    status: ListingStatus
    rejection_reason: str | None = None
    submitted_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class HookListingSummary(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    event: str
    scope: str
    owner: str
    status: ListingStatus
    model_config = {"from_attributes": True}


class HookInstallRequest(BaseModel):
    ide: str


class HookInstallResponse(BaseModel):
    listing_id: uuid.UUID
    ide: str
    config_snippet: dict
