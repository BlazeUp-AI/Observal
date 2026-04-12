"""Materializer: converts otel_logs hook events into eval-compatible spans.

Kiro CLI (and other hook-based sources) write flat log entries to otel_logs.
The eval pipeline expects structured spans with type/input/output/status.
This module bridges that gap by reading hook events for a session and
synthesizing span dicts that StructuralScorer and SLMScorer can consume.
"""

import logging
import uuid
from datetime import datetime

from services.clickhouse import _escape, _query

logger = logging.getLogger(__name__)


async def materialize_session_spans(session_id: str) -> tuple[dict, list[dict]]:
    """Convert otel_logs hook events for a session into a trace + spans.

    Returns:
        (trace_dict, spans_list) compatible with run_structured_eval().
    """
    sid = _escape(session_id)
    # Fetch by session.id OR conversation_id to handle Kiro resumed sessions
    sql = (
        "SELECT "
        "Timestamp AS timestamp, "
        "EventName AS event_name, "
        "Body AS body, "
        "LogAttributes AS attributes, "
        "ServiceName AS service_name "
        "FROM otel_logs "
        f"WHERE LogAttributes['session.id'] = '{sid}' "
        f"OR LogAttributes['conversation_id'] = '{sid}' "
        "ORDER BY Timestamp ASC "
        "FORMAT JSON"
    )

    try:
        r = await _query(sql)
        r.raise_for_status()
        events = r.json().get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch hook events for session {session_id}: {e}")
        return {}, []

    if not events:
        return {}, []

    return _build_trace_and_spans(session_id, events)


def _build_trace_and_spans(
    session_id: str, events: list[dict]
) -> tuple[dict, list[dict]]:
    """Parse hook events into a trace dict and span list."""
    spans: list[dict] = []
    trace_output = ""
    model = ""
    agent_name = ""
    first_ts = events[0].get("timestamp", "")
    last_ts = events[-1].get("timestamp", "")

    # Pair PreToolUse with PostToolUse events by matching sequence
    pending_pre: dict | None = None

    for event in events:
        attrs = event.get("attributes", {})
        if isinstance(attrs, str):
            import json

            try:
                attrs = json.loads(attrs)
            except Exception:
                attrs = {}

        event_name = _normalize_event_name(
            attrs.get("event.name", event.get("event_name", ""))
        )

        if not model and attrs.get("model"):
            model = attrs["model"]
        if not agent_name and attrs.get("agent_name"):
            agent_name = attrs["agent_name"]

        if event_name in ("hook_PreToolUse", "PreToolUse"):
            pending_pre = {
                "timestamp": event.get("timestamp", ""),
                "tool_name": attrs.get("tool_name", "unknown"),
                "tool_input": attrs.get("tool_input", event.get("body", "")),
            }

        elif event_name in ("hook_PostToolUse", "PostToolUse", "hook_PostToolUseFailure"):
            tool_name = attrs.get("tool_name", "")
            tool_input = ""
            tool_output = attrs.get("tool_response", event.get("body", ""))
            start_ts = event.get("timestamp", "")
            is_error = "Failure" in event_name or attrs.get("error", "")

            if pending_pre:
                tool_name = tool_name or pending_pre["tool_name"]
                tool_input = pending_pre["tool_input"]
                start_ts = pending_pre["timestamp"]
                pending_pre = None

            latency_ms = _compute_latency(start_ts, event.get("timestamp", ""))

            spans.append({
                "span_id": str(uuid.uuid4())[:16],
                "type": "tool_call",
                "name": tool_name,
                "input": _truncate(tool_input, 2000),
                "output": _truncate(tool_output, 2000),
                "status": "error" if is_error else "success",
                "error": attrs.get("error", "") if is_error else None,
                "latency_ms": latency_ms,
                "start_time": start_ts,
            })

        elif event_name in ("hook_UserPromptSubmit", "UserPromptSubmit", "user_prompt"):
            prompt_text = (
                attrs.get("tool_input", "")
                or attrs.get("prompt", "")
                or event.get("body", "")
            )
            spans.append({
                "span_id": str(uuid.uuid4())[:16],
                "type": "user_prompt",
                "name": "user_prompt",
                "input": _truncate(prompt_text, 2000),
                "output": "",
                "status": "success",
                "error": None,
                "latency_ms": 0,
                "start_time": event.get("timestamp", ""),
            })

        elif event_name in ("hook_Stop", "Stop"):
            response = (
                attrs.get("tool_response", "")
                or attrs.get("assistant_response", "")
                or event.get("body", "")
            )
            trace_output = _truncate(response, 4000)
            spans.append({
                "span_id": str(uuid.uuid4())[:16],
                "type": "agent_response",
                "name": "final_response",
                "input": "",
                "output": trace_output,
                "status": "success",
                "error": None,
                "latency_ms": 0,
                "start_time": event.get("timestamp", ""),
            })

        elif event_name in ("hook_SessionStart", "SessionStart", "agentSpawn"):
            spans.append({
                "span_id": str(uuid.uuid4())[:16],
                "type": "session_start",
                "name": "session_start",
                "input": event.get("body", ""),
                "output": "",
                "status": "success",
                "error": None,
                "latency_ms": 0,
                "start_time": event.get("timestamp", ""),
            })

    # Build the trace dict
    trace = {
        "trace_id": session_id,
        "event_id": session_id,
        "agent_id": agent_name,
        "model": model,
        "output": trace_output,
        "status": "completed",
        "start_time": first_ts,
        "end_time": last_ts,
        "span_count": len(spans),
        "tool_calls": sum(1 for s in spans if s["type"] == "tool_call"),
        "source": "hook_materializer",
    }

    return trace, spans


def _normalize_event_name(name: str) -> str:
    """Normalize event names to a consistent form."""
    # Already normalized
    if name.startswith("hook_") or name in (
        "PreToolUse", "PostToolUse", "UserPromptSubmit",
        "Stop", "SessionStart",
    ):
        return name
    # camelCase Kiro events
    mapping = {
        "preToolUse": "PreToolUse",
        "postToolUse": "PostToolUse",
        "userPromptSubmit": "UserPromptSubmit",
        "stop": "Stop",
        "agentSpawn": "SessionStart",
    }
    return mapping.get(name, name)


def _compute_latency(start: str, end: str) -> int:
    """Compute latency in ms between two ISO timestamps."""
    try:
        fmt = "%Y-%m-%d %H:%M:%S.%f"
        # ClickHouse timestamps may have various formats
        for f in (fmt, "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                t_start = datetime.strptime(start[:26], f)
                t_end = datetime.strptime(end[:26], f)
                return max(0, int((t_end - t_start).total_seconds() * 1000))
            except ValueError:
                continue
    except Exception:
        pass
    return 0


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len chars."""
    if not text:
        return ""
    text = str(text)
    return text[:max_len] if len(text) > max_len else text
