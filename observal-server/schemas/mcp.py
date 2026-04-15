import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from models.mcp import ListingStatus
from schemas.constants import VALID_MCP_CATEGORIES, VALID_MCP_FRAMEWORKS, make_ide_list_validator, make_option_validator


class McpEnvVar(BaseModel):
    name: str
    description: str = ""
    required: bool = True


def _coerce_env_vars(v):
    """Coerce None → [] so DB NULLs don't break serialization."""
    return v or []


class ClientAnalysis(BaseModel):
    """Analysis results produced client-side (CLI local clone)."""

    tools: list[dict] = []
    issues: list[str] = []
    framework: str = ""
    entry_point: str = ""


class McpSubmitRequest(BaseModel):
    git_url: str
    name: str
    version: str
    description: str = ""
    category: str
    owner: str
    framework: str | None = None
    docker_image: str | None = None
    supported_ides: list[str] = []
    environment_variables: list[McpEnvVar] = []
    setup_instructions: str | None = None
    changelog: str | None = None
    custom_fields: dict[str, str] = {}
    client_analysis: ClientAnalysis | None = None

    _validate_category = field_validator("category")(make_option_validator("category", VALID_MCP_CATEGORIES))

    @field_validator("framework")
    @classmethod
    def _validate_framework(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_MCP_FRAMEWORKS:
            raise ValueError(f"Invalid framework '{v}'. Valid options: {', '.join(VALID_MCP_FRAMEWORKS)}")
        return v

    _validate_ides = field_validator("supported_ides")(make_ide_list_validator())


class McpCustomFieldResponse(BaseModel):
    field_name: str
    field_value: str
    model_config = {"from_attributes": True}


class McpValidationResultResponse(BaseModel):
    stage: str
    passed: bool
    details: str | None
    run_at: datetime
    model_config = {"from_attributes": True}


class McpListingResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    git_url: str
    description: str
    category: str
    owner: str
    supported_ides: list[str]
    environment_variables: list[McpEnvVar] = []
    setup_instructions: str | None
    changelog: str | None
    framework: str | None = None
    docker_image: str | None = None
    mcp_validated: bool = False

    _coerce_env = field_validator("environment_variables", mode="before")(_coerce_env_vars)
    status: ListingStatus
    rejection_reason: str | None = None
    submitted_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    custom_fields: list[McpCustomFieldResponse] = []
    validation_results: list[McpValidationResultResponse] = []

    model_config = {"from_attributes": True}


class McpListingSummary(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    category: str
    owner: str
    supported_ides: list[str]
    status: ListingStatus

    model_config = {"from_attributes": True}


class McpInstallRequest(BaseModel):
    ide: str
    env_values: dict[str, str] = {}


class McpInstallResponse(BaseModel):
    listing_id: uuid.UUID
    ide: str
    config_snippet: dict


class McpAnalyzeRequest(BaseModel):
    git_url: str


class McpAnalyzeResponse(BaseModel):
    name: str
    description: str
    version: str
    tools: list[dict]
    environment_variables: list[McpEnvVar] = []
    issues: list[str] = []
    error: str = ""

    _coerce_env = field_validator("environment_variables", mode="before")(_coerce_env_vars)


class ReviewActionRequest(BaseModel):
    reason: str | None = None
