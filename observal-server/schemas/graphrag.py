import uuid
from datetime import datetime

from pydantic import BaseModel

from models.mcp import ListingStatus


class GraphRagSubmitRequest(BaseModel):
    name: str
    version: str
    description: str
    owner: str
    endpoint_url: str
    auth_type: str = "none"
    auth_config: dict | None = None
    query_interface: str
    graph_schema: dict | None = None
    data_sources: list[dict] = []
    embedding_model: str | None = None
    chunk_strategy: str | None = None
    supported_ides: list[str] = []


class GraphRagListingResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    owner: str
    endpoint_url: str
    auth_type: str
    query_interface: str
    supported_ides: list[str]
    status: ListingStatus
    rejection_reason: str | None = None
    submitted_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class GraphRagListingSummary(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    query_interface: str
    owner: str
    supported_ides: list[str]
    status: ListingStatus
    model_config = {"from_attributes": True}


class GraphRagInstallRequest(BaseModel):
    ide: str


class GraphRagInstallResponse(BaseModel):
    listing_id: uuid.UUID
    ide: str
    config_snippet: dict
