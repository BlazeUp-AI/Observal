import uuid
from datetime import datetime

from pydantic import BaseModel

from models.mcp import ListingStatus


class PromptSubmitRequest(BaseModel):
    name: str
    version: str
    description: str
    owner: str
    category: str
    template: str
    variables: list[dict] = []
    model_hints: dict | None = None
    tags: list[str] = []
    supported_ides: list[str] = []


class PromptListingResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    owner: str
    category: str
    template: str
    variables: list[dict]
    tags: list[str]
    supported_ides: list[str]
    status: ListingStatus
    rejection_reason: str | None = None
    submitted_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class PromptListingSummary(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    category: str
    owner: str
    status: ListingStatus
    model_config = {"from_attributes": True}


class PromptRenderRequest(BaseModel):
    variables: dict[str, str] = {}


class PromptRenderResponse(BaseModel):
    listing_id: uuid.UUID
    rendered: str
