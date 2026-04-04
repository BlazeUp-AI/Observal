import uuid
from datetime import datetime

from pydantic import BaseModel

from models.mcp import ListingStatus


class SkillSubmitRequest(BaseModel):
    name: str
    version: str
    description: str
    owner: str
    git_url: str | None = None
    skill_path: str = "/"
    archive_url: str | None = None
    target_agents: list[str] = []
    task_type: str
    triggers: dict | None = None
    slash_command: str | None = None
    has_scripts: bool = False
    has_templates: bool = False
    supported_ides: list[str] = []
    is_power: bool = False
    power_md: str | None = None
    mcp_server_config: dict | None = None
    activation_keywords: list[str] | None = None


class SkillListingResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    owner: str
    git_url: str | None
    task_type: str
    target_agents: list[str]
    supported_ides: list[str]
    is_power: bool
    status: ListingStatus
    rejection_reason: str | None = None
    submitted_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class SkillListingSummary(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    task_type: str
    owner: str
    target_agents: list[str]
    status: ListingStatus
    model_config = {"from_attributes": True}


class SkillInstallRequest(BaseModel):
    ide: str


class SkillInstallResponse(BaseModel):
    listing_id: uuid.UUID
    ide: str
    config_snippet: dict
