from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AlertRuleCreate(BaseModel):
    name: str
    metric: str  # error_rate | latency_p99 | token_usage
    threshold: float
    condition: str  # above | below
    target_type: str = "all"  # mcp | agent | all
    target_id: str = ""
    webhook_url: str = ""


class AlertRuleUpdate(BaseModel):
    status: str  # active | paused


class AlertRuleResponse(BaseModel):
    id: UUID
    name: str
    metric: str
    threshold: float
    condition: str
    target_type: str
    target_id: str
    webhook_url: str
    status: str
    last_triggered: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
