import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Request

from api.deps import get_project_id, require_role
from models.user import User, UserRole
from schemas.telemetry import (
    IngestBatch,
    IngestResponse,
    TelemetryBatch,
    TelemetryStatusResponse,
)
from services.clickhouse import (
    insert_agent_interaction,
    insert_otel_logs,
    insert_scores,
    insert_spans,
    insert_tool_call,
    insert_traces,
    query_recent_events,
)
from services.redis import publish
from services.secrets_redactor import redact_secrets

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])

# Background tasks that must survive until completion (prevent GC)
_background_tasks: set[asyncio.Task] = set()


# Shim span type → otel_logs event.name mapping
_SHIM_EVENT_NAMES: dict[str, str] = {
    "tool_call": "shim_tool_call",
    "tool_list": "shim_tool_list",
    "initialize": "shim_initialize",
    "resource_read": "shim_resource_read",
    "resource_list": "shim_resource_list",
    "resource_subscribe": "shim_resource_subscribe",
    "prompt_get": "shim_prompt_get",
    "prompt_list": "shim_prompt_list",
    "ping": "shim_ping",
    "completion": "shim_completion",
    "config": "shim_config",
    "other": "shim_other",
}


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    batch: IngestBatch,
    current_user: User = Depends(require_role(UserRole.user)),
    x_observal_environment: str = Header("default"),
):
    """New ingestion endpoint for shim/proxy telemetry."""
    user_id = str(current_user.id)
    project_id = get_project_id(current_user)
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
                        "project_id": project_id,
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
                        "input": redact_secrets(t.input) if t.input else t.input,
                        "output": redact_secrets(t.output) if t.output else t.output,
                        "tool_id": t.tool_id,
                        "sandbox_id": t.sandbox_id,
                        "graphrag_id": t.graphrag_id,
                        "hook_id": t.hook_id,
                        "skill_id": t.skill_id,
                        "prompt_id": t.prompt_id,
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
                        "project_id": project_id,
                        "mcp_id": None,
                        "agent_id": None,
                        "user_id": user_id,
                        "type": s.type,
                        "name": s.name,
                        "method": s.method,
                        "input": redact_secrets(s.input) if s.input else s.input,
                        "output": redact_secrets(s.output) if s.output else s.output,
                        "error": redact_secrets(s.error) if s.error else s.error,
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
                        "container_id": s.container_id,
                        "exit_code": s.exit_code,
                        "network_bytes_in": s.network_bytes_in,
                        "network_bytes_out": s.network_bytes_out,
                        "disk_read_bytes": s.disk_read_bytes,
                        "disk_write_bytes": s.disk_write_bytes,
                        "oom_killed": (int(s.oom_killed) if s.oom_killed is not None else None),
                        "query_interface": s.query_interface,
                        "relevance_score": s.relevance_score,
                        "chunks_returned": s.chunks_returned,
                        "embedding_latency_ms": s.embedding_latency_ms,
                        "hook_event": s.hook_event,
                        "hook_scope": s.hook_scope,
                        "hook_action": s.hook_action,
                        "hook_blocked": (int(s.hook_blocked) if s.hook_blocked is not None else None),
                        "variables_provided": s.variables_provided,
                        "template_tokens": s.template_tokens,
                        "rendered_tokens": s.rendered_tokens,
                    }
                )
            await insert_spans(rows)
            ingested += len(rows)
        except Exception:
            logger.exception("Failed to insert spans")
            errors += len(batch.spans)

    # --- Mirror shim spans into otel_logs for unified session view ---
    if batch.spans and batch.traces:
        try:
            # Build a lookup of trace metadata for session_id / mcp_id
            trace_meta: dict[str, dict] = {}
            for t in batch.traces:
                trace_meta[t.trace_id] = {
                    "session_id": t.session_id or "",
                    "mcp_id": t.mcp_id or "",
                    "agent_id": t.agent_id or "",
                    "ide": t.ide or "",
                }

            otel_rows = []
            for s in batch.spans:
                meta = trace_meta.get(s.trace_id, {})
                session_id = meta.get("session_id", "")
                if not session_id:
                    continue  # Can't place in a session — skip

                event_name = _SHIM_EVENT_NAMES.get(s.type or "", "shim_other")
                mcp_id = meta.get("mcp_id", "")
                tool_name = s.name or ""

                # Build a human-readable body
                latency_label = f" ({s.latency_ms}ms)" if s.latency_ms else ""
                body_text = f"shim: {s.type} {tool_name}{latency_label}"

                attrs: dict[str, str] = {
                    "session.id": session_id,
                    "event.name": event_name,
                    "source": "shim",
                    "tool_name": tool_name,
                    "mcp_id": mcp_id,
                    "mcp_method": s.method or "",
                    "mcp_span_id": s.span_id or "",
                    "mcp_trace_id": s.trace_id or "",
                }
                if s.latency_ms is not None:
                    attrs["mcp_latency_ms"] = str(s.latency_ms)
                if s.tool_schema_valid is not None:
                    attrs["tool_schema_valid"] = str(int(s.tool_schema_valid))
                if s.tools_available is not None:
                    attrs["tools_available"] = str(s.tools_available)
                if s.input:
                    attrs["mcp_input"] = redact_secrets(s.input)
                if s.output:
                    attrs["mcp_output"] = redact_secrets(s.output)
                if s.error:
                    attrs["mcp_error"] = redact_secrets(s.error)
                if s.status:
                    attrs["mcp_status"] = s.status
                if meta.get("agent_id"):
                    attrs["agent_id"] = meta["agent_id"]
                if meta.get("ide"):
                    attrs["terminal.type"] = meta["ide"]

                otel_rows.append(
                    {
                        "Timestamp": s.start_time or now,
                        "Body": body_text,
                        "LogAttributes": attrs,
                        "ServiceName": "observal-shim",
                        "SeverityText": "ERROR" if s.status == "error" else "INFO",
                        "SeverityNumber": 17 if s.status == "error" else 9,
                        "TraceId": s.trace_id or "",
                        "SpanId": s.span_id or "",
                    }
                )

            if otel_rows:
                await insert_otel_logs(otel_rows)

                # Notify subscribers so session detail updates live
                session_ids_seen: set[str] = set()
                for row in otel_rows:
                    sid = row["LogAttributes"].get("session.id", "")
                    if sid and sid not in session_ids_seen:
                        session_ids_seen.add(sid)
                        task = asyncio.create_task(
                            publish("sessions:updated", {"session_id": sid, "event_name": "shim_ingest"})
                        )
                        _background_tasks.add(task)
                        task.add_done_callback(_background_tasks.discard)
        except Exception:
            logger.exception("Failed to mirror shim spans to otel_logs")

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
                        "project_id": project_id,
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
    current_user: User = Depends(require_role(UserRole.user)),
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
                    "input_params": redact_secrets(tc.input_params) if tc.input_params else tc.input_params,
                    "response": redact_secrets(tc.response) if tc.response else tc.response,
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
async def telemetry_status(current_user: User = Depends(require_role(UserRole.admin))):
    counts = await query_recent_events(60)
    return TelemetryStatusResponse(
        tool_call_events=counts["tool_call_events"],
        agent_interaction_events=counts["agent_interaction_events"],
        status="ok",
    )


# Kiro CLI uses camelCase event names; normalize to PascalCase
_KIRO_EVENT_MAP = {
    "agentSpawn": "SessionStart",
    "userPromptSubmit": "UserPromptSubmit",
    "promptSubmit": "UserPromptSubmit",
    "preToolUse": "PreToolUse",
    "postToolUse": "PostToolUse",
    "stop": "Stop",
    "agentStop": "Stop",
}


@router.post("/hooks")
async def ingest_hook(request: Request, current_user: User = Depends(require_role(UserRole.user))):
    """Ingest raw hook JSON from Claude Code/Kiro."""
    project_id = get_project_id(current_user)
    body = await request.json()

    # Normalize Kiro camelCase field names to snake_case
    if "hookEventName" in body and "hook_event_name" not in body:
        body["hook_event_name"] = body["hookEventName"]
    if "toolName" in body and "tool_name" not in body:
        body["tool_name"] = body["toolName"]
    if "toolInput" in body and "tool_input" not in body:
        body["tool_input"] = body["toolInput"]
    if "toolResponse" in body and "tool_response" not in body:
        body["tool_response"] = body["toolResponse"]
    if "sessionId" in body and "session_id" not in body:
        body["session_id"] = body["sessionId"]

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    raw_event = body.get("hook_event_name", "unknown")
    hook_event_name = _KIRO_EVENT_MAP.get(raw_event, raw_event)
    tool_name = body.get("tool_name", "")
    if tool_name in ("assistant_response", "assistant_thinking"):
        span_type = f"hook_{tool_name}"
    elif hook_event_name == "PostToolUse":
        span_type = "hook_exec"
    else:
        span_type = f"hook_{hook_event_name.lower()}"
    row = {
        "span_id": str(uuid.uuid4()),
        "trace_id": body.get("session_id", str(uuid.uuid4())),
        "parent_span_id": None,
        "project_id": project_id,
        "mcp_id": None,
        "agent_id": None,
        "user_id": str(current_user.id),
        "type": span_type,
        "name": body.get("tool_name", "hook"),
        "method": "",
        "input": body.get("tool_input"),
        "output": body.get("tool_response"),
        "error": None,
        "start_time": now,
        "end_time": now,
        "latency_ms": None,
        "status": "success",
        "ide": "",
        "environment": "default",
        "metadata": {},
        "token_count_input": None,
        "token_count_output": None,
        "token_count_total": None,
        "cost": None,
        "cpu_ms": None,
        "memory_mb": None,
        "hop_count": None,
        "entities_retrieved": None,
        "relationships_used": None,
        "retry_count": None,
        "tools_available": None,
        "tool_schema_valid": None,
        "container_id": None,
        "exit_code": None,
        "network_bytes_in": None,
        "network_bytes_out": None,
        "disk_read_bytes": None,
        "disk_write_bytes": None,
        "oom_killed": None,
        "query_interface": None,
        "relevance_score": None,
        "chunks_returned": None,
        "embedding_latency_ms": None,
        "hook_event": hook_event_name,
        "hook_scope": None,
        "hook_action": None,
        "hook_blocked": None,
        "variables_provided": None,
        "template_tokens": None,
        "rendered_tokens": None,
    }
    await insert_spans([row])
    return {"ingested": 1}
