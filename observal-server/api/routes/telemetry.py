import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header

from api.deps import get_current_user
from models.user import User
from schemas.telemetry import (
    IngestBatch,
    IngestResponse,
    TelemetryBatch,
    TelemetryStatusResponse,
)
from services.clickhouse import (
    insert_agent_interaction,
    insert_scores,
    insert_spans,
    insert_tool_call,
    insert_traces,
    query_recent_events,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])

DEFAULT_PROJECT = "default"


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    batch: IngestBatch,
    current_user: User = Depends(get_current_user),
    x_observal_environment: str = Header("default"),
):
    """New ingestion endpoint for shim/proxy telemetry."""
    user_id = str(current_user.id)
    environment = x_observal_environment or "default"
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    ingested = 0
    errors = 0

    # --- Traces ---
    if batch.traces:
        try:
            rows = []
            for t in batch.traces:
                rows.append(
                    {
                        "trace_id": t.trace_id,
                        "parent_trace_id": t.parent_trace_id,
                        "project_id": DEFAULT_PROJECT,
                        "mcp_id": t.mcp_id,
                        "agent_id": t.agent_id,
                        "user_id": user_id,
                        "session_id": t.session_id,
                        "ide": t.ide,
                        "environment": environment,
                        "start_time": t.start_time,
                        "end_time": t.end_time,
                        "trace_type": t.trace_type,
                        "name": t.name,
                        "metadata": t.metadata,
                        "tags": t.tags,
                        "input": t.input,
                        "output": t.output,
                    }
                )
            await insert_traces(rows)
            ingested += len(rows)
        except Exception:
            logger.exception("Failed to insert traces")
            errors += len(batch.traces)

    # --- Spans ---
    if batch.spans:
        try:
            rows = []
            for s in batch.spans:
                rows.append(
                    {
                        "span_id": s.span_id,
                        "trace_id": s.trace_id,
                        "parent_span_id": s.parent_span_id,
                        "project_id": DEFAULT_PROJECT,
                        "mcp_id": None,
                        "agent_id": None,
                        "user_id": user_id,
                        "type": s.type,
                        "name": s.name,
                        "method": s.method,
                        "input": s.input,
                        "output": s.output,
                        "error": s.error,
                        "start_time": s.start_time,
                        "end_time": s.end_time,
                        "latency_ms": s.latency_ms,
                        "status": s.status,
                        "ide": s.ide,
                        "environment": environment,
                        "metadata": s.metadata,
                        "token_count_input": s.token_count_input,
                        "token_count_output": s.token_count_output,
                        "token_count_total": s.token_count_total,
                        "cost": s.cost,
                        "cpu_ms": s.cpu_ms,
                        "memory_mb": s.memory_mb,
                        "hop_count": s.hop_count,
                        "entities_retrieved": s.entities_retrieved,
                        "relationships_used": s.relationships_used,
                        "retry_count": s.retry_count,
                        "tools_available": s.tools_available,
                        "tool_schema_valid": (int(s.tool_schema_valid) if s.tool_schema_valid is not None else None),
                    }
                )
            await insert_spans(rows)
            ingested += len(rows)
        except Exception:
            logger.exception("Failed to insert spans")
            errors += len(batch.spans)

    # --- Scores ---
    if batch.scores:
        try:
            rows = []
            for sc in batch.scores:
                rows.append(
                    {
                        "score_id": sc.score_id,
                        "trace_id": sc.trace_id,
                        "span_id": sc.span_id,
                        "project_id": DEFAULT_PROJECT,
                        "mcp_id": sc.mcp_id,
                        "agent_id": sc.agent_id,
                        "user_id": user_id,
                        "name": sc.name,
                        "source": sc.source,
                        "data_type": sc.data_type,
                        "value": sc.value,
                        "string_value": sc.string_value,
                        "comment": sc.comment,
                        "metadata": sc.metadata,
                        "timestamp": now,
                    }
                )
            await insert_scores(rows)
            ingested += len(rows)
        except Exception:
            logger.exception("Failed to insert scores")
            errors += len(batch.scores)

    return IngestResponse(ingested=ingested, errors=errors)


@router.post("/events")
async def ingest_events(
    batch: TelemetryBatch,
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    ingested = 0
    errors = 0

    for tc in batch.tool_calls:
        try:
            await insert_tool_call(
                {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": now,
                    "mcp_server_id": tc.mcp_server_id,
                    "tool_name": tc.tool_name,
                    "input_params": tc.input_params,
                    "response": tc.response,
                    "latency_ms": tc.latency_ms,
                    "status": tc.status,
                    "user_action": tc.user_action,
                    "session_id": tc.session_id,
                    "user_id": str(current_user.id),
                    "ide": tc.ide,
                }
            )
            ingested += 1
        except Exception:
            errors += 1

    for ai in batch.agent_interactions:
        try:
            await insert_agent_interaction(
                {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": now,
                    "agent_id": ai.agent_id,
                    "session_id": ai.session_id,
                    "tool_calls": ai.tool_calls,
                    "user_action": ai.user_action,
                    "latency_ms": ai.latency_ms,
                    "user_id": str(current_user.id),
                    "ide": ai.ide,
                }
            )
            ingested += 1
        except Exception:
            errors += 1

    return {"ingested": ingested, "errors": errors}


@router.get("/status", response_model=TelemetryStatusResponse)
async def telemetry_status(current_user: User = Depends(get_current_user)):
    counts = await query_recent_events(60)
    return TelemetryStatusResponse(
        tool_call_events=counts["tool_call_events"],
        agent_interaction_events=counts["agent_interaction_events"],
        status="ok",
    )
