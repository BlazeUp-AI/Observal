"""Session reconciliation endpoint — accepts enrichment data from CLI
after parsing local session JSONL files."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from services.clickhouse import _query, insert_otel_logs

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


class ReconcilePayload(BaseModel):
    """Enrichment data for a single session."""

    session_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    models_used: list[str] = []
    primary_model: str | None = None
    total_cost_usd: float = 0.0
    service_tier: str | None = None
    conversation_turns: int = 0
    tool_use_count: int = 0
    thinking_turns: int = 0
    stop_reasons: dict[str, int] = {}
    completeness_score: float = 1.0
    per_turn: list[dict] = []


@router.post("/reconcile")
async def reconcile_session(
    payload: ReconcilePayload,
    request: Request,
    x_observal_user_id: str | None = Header(None),
):
    """Accept session enrichment data and merge into ClickHouse.

    This endpoint receives parsed session file data from the CLI and
    inserts enrichment records into otel_logs for the session. The
    enrichment data includes per-turn token counts, model info, and
    cost data that hooks alone cannot capture.
    """
    session_id = payload.session_id
    user_id = x_observal_user_id or "unknown"

    # Check if session exists in ClickHouse
    check_sql = """
        SELECT count() as cnt
        FROM otel_logs
        WHERE LogAttributes['session.id'] = {sid:String}
        LIMIT 1
        FORMAT JSON
    """
    try:
        resp = await _query(check_sql, {"param_sid": session_id})
        resp.raise_for_status()
        data = resp.json().get("data", [])
        existing_count = int(data[0]["cnt"]) if data else 0
    except Exception as e:
        logger.warning("reconcile_check_failed", session_id=session_id, error=str(e))
        existing_count = 0

    if existing_count == 0:
        logger.info("reconcile_no_existing_session", session_id=session_id)
        return {"status": "skipped", "reason": "no existing session data found"}

    # Check if already reconciled (avoid duplicates)
    recon_check_sql = """
        SELECT count() as cnt
        FROM otel_logs
        WHERE LogAttributes['session.id'] = {sid:String}
          AND LogAttributes['event.name'] = 'reconcile_enrichment'
        LIMIT 1
        FORMAT JSON
    """
    try:
        resp = await _query(recon_check_sql, {"param_sid": session_id})
        resp.raise_for_status()
        data = resp.json().get("data", [])
        already_reconciled = int(data[0]["cnt"]) if data else 0
    except Exception:
        already_reconciled = 0

    if already_reconciled > 0:
        return {"status": "skipped", "reason": "session already reconciled"}

    # Insert enrichment as a special otel_logs record
    import json
    from datetime import UTC, datetime

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")

    enrichment_row = {
        "Timestamp": now,
        "TraceId": "",
        "SpanId": "",
        "SeverityText": "INFO",
        "SeverityNumber": 9,
        "ServiceName": "reconcile",
        "Body": f"Session reconciliation: {payload.conversation_turns} turns, {payload.primary_model or 'unknown'}",
        "LogAttributes": {
            "session.id": session_id,
            "event.name": "reconcile_enrichment",
            "user.id": user_id,
            "input_tokens": str(payload.total_input_tokens),
            "output_tokens": str(payload.total_output_tokens),
            "cache_read_tokens": str(payload.total_cache_read_tokens),
            "cache_creation_tokens": str(payload.total_cache_creation_tokens),
            "model": payload.primary_model or "",
            "models_used": ",".join(payload.models_used),
            "total_cost_usd": f"{payload.total_cost_usd:.6f}",
            "service_tier": payload.service_tier or "",
            "conversation_turns": str(payload.conversation_turns),
            "tool_use_count": str(payload.tool_use_count),
            "thinking_turns": str(payload.thinking_turns),
            "stop_reasons": json.dumps(payload.stop_reasons),
            "completeness_score": f"{payload.completeness_score:.2f}",
            "per_turn_count": str(len(payload.per_turn)),
            "reconciled": "true",
        },
    }

    # Also insert per-turn records for detailed analysis
    rows = [enrichment_row]

    for turn in payload.per_turn[:50]:  # Cap at 50 turns
        turn_row = {
            "Timestamp": now,
            "TraceId": "",
            "SpanId": "",
            "SeverityText": "INFO",
            "SeverityNumber": 9,
            "ServiceName": "reconcile",
            "Body": f"Turn {turn.get('turn_index', 0)}: {turn.get('model', 'unknown')}",
            "LogAttributes": {
                "session.id": session_id,
                "event.name": "reconcile_turn",
                "user.id": user_id,
                "turn_index": str(turn.get("turn_index", 0)),
                "model": turn.get("model") or "",
                "stop_reason": turn.get("stop_reason") or "",
                "input_tokens": str(turn.get("input_tokens", 0)),
                "output_tokens": str(turn.get("output_tokens", 0)),
                "cache_read_tokens": str(turn.get("cache_read_tokens", 0)),
                "cache_creation_tokens": str(turn.get("cache_creation_tokens", 0)),
                "has_thinking": "true" if turn.get("has_thinking") else "false",
                "tool_uses": ",".join(turn.get("tool_uses", [])),
                "reconciled": "true",
            },
        }
        rows.append(turn_row)

    try:
        await insert_otel_logs(rows)
        logger.info(
            "reconcile_success",
            session_id=session_id,
            turns=payload.conversation_turns,
            cost_usd=payload.total_cost_usd,
            rows_inserted=len(rows),
        )
    except Exception as e:
        logger.error("reconcile_insert_failed", session_id=session_id, error=str(e))
        return {"status": "error", "reason": str(e)}

    return {
        "status": "reconciled",
        "session_id": session_id,
        "turns_ingested": len(payload.per_turn),
        "total_cost_usd": payload.total_cost_usd,
    }
