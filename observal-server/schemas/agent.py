import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from models.agent import AgentStatus


class GoalSectionRequest(BaseModel):
    name: str
    description: str | None = None
    grounding_required: bool = False


class GoalTemplateRequest(BaseModel):
    description: str
    sections: list[GoalSectionRequest] = Field(min_length=1)


class ExternalMcp(BaseModel):
    name: str
    command: str = "npx"
    args: list[str] = []
    env: dict[str, str] = {}
    url: str | None = None  # source URL for reference


class AgentCreateRequest(BaseModel):
    name: str
    version: str
    description: str = ""
    owner: str
    prompt: str = ""
    model_name: str
    model_config_json: dict = {}
    supported_ides: list[str] = []
    mcp_server_ids: list[uuid.UUID] = []
    external_mcps: list[ExternalMcp] = []
    goal_template: GoalTemplateRequest


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    version: str | None = None
    description: str | None = None
    owner: str | None = None
    prompt: str | None = None
    model_name: str | None = None
    model_config_json: dict | None = None
    supported_ides: list[str] | None = None
    mcp_server_ids: list[uuid.UUID] | None = None
    external_mcps: list[ExternalMcp] | None = None
    goal_template: GoalTemplateRequest | None = None


class GoalSectionResponse(BaseModel):
    name: str
    description: str | None
    grounding_required: bool
    order: int
    model_config = {"from_attributes": True}


class GoalTemplateResponse(BaseModel):
    description: str
    sections: list[GoalSectionResponse] = []
    model_config = {"from_attributes": True}


class McpLinkResponse(BaseModel):
    mcp_listing_id: uuid.UUID
    mcp_name: str
    order: int
    model_config = {"from_attributes": True}


class AgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    owner: str
    prompt: str
    model_name: str
    model_config_json: dict
    external_mcps: list = []
    supported_ides: list[str]
    status: AgentStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    mcp_links: list[McpLinkResponse] = []
    goal_template: GoalTemplateResponse | None = None

    model_config = {"from_attributes": True}


class AgentSummary(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    owner: str
    model_name: str
    supported_ides: list[str]
    status: AgentStatus
    model_config = {"from_attributes": True}


class AgentInstallRequest(BaseModel):
    ide: str


class AgentInstallResponse(BaseModel):
    agent_id: uuid.UUID
    ide: str
    config_snippet: dict
