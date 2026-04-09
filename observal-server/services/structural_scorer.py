"""Structural scorer: rule-based scoring for Tool Efficiency and Tool Failures.

Parses spans from ClickHouse to detect penalties without needing an LLM.
"""

import hashlib
import json
import logging

from models.scoring import ScoringDimension

logger = logging.getLogger(__name__)

# Timeout threshold in ms for tool calls
DEFAULT_TIMEOUT_MS = 30_000
# Default median tool calls for new agents
DEFAULT_MEDIAN_TOOL_CALLS = 10


class StructuralScorer:
    """Rule-based scorer for tool_efficiency and tool_failures dimensions."""

    def __init__(self, timeout_ms: int = DEFAULT_TIMEOUT_MS):
        self.timeout_ms = timeout_ms

    def score_tool_efficiency(
        self,
        spans: list[dict],
        agent_id: str,
        has_linked_mcps: bool = True,
        historical_median: float | None = None,
    ) -> list[dict]:
        """Detect tool efficiency penalties from spans.

        Returns list of dicts with keys: event_name, evidence, trace_event_index.
        """
        penalties: list[dict] = []
        tool_call_spans = [s for s in spans if s.get("type") == "tool_call"]

        # Zero tool calls when agent has linked MCPs
        if has_linked_mcps and len(tool_call_spans) == 0:
            penalties.append({
                "event_name": "zero_tool_calls_when_needed",
                "dimension": ScoringDimension.tool_efficiency,
                "evidence": f"Agent {agent_id} has linked MCPs but trace contains 0 tool call spans.",
                "trace_event_index": None,
            })
            return penalties

        # Duplicate tool calls: same tool name + same input hash
        seen: dict[str, int] = {}
        for idx, span in enumerate(tool_call_spans):
            key = _span_dedup_key(span)
            if key in seen:
                penalties.append({
                    "event_name": "duplicate_tool_call",
                    "dimension": ScoringDimension.tool_efficiency,
                    "evidence": (
                        f"Duplicate call to '{span.get('name', '')}' with same params. "
                        f"First at index {seen[key]}, duplicate at index {idx}."
                    ),
                    "trace_event_index": idx,
                })
            else:
                seen[key] = idx

        # Unused tool results: tool output not referenced by any subsequent span
        for idx, span in enumerate(tool_call_spans):
            output = span.get("output") or ""
            if not output:
                continue
            global_idx = spans.index(span) if span in spans else -1
            subsequent = spans[global_idx + 1:] if global_idx >= 0 else []
            if not subsequent:
                continue  # last span — nothing can reference it
            referenced = False
            for later in subsequent:
                later_input = later.get("input") or ""
                if output[:50] in later_input:
                    referenced = True
                    break
            if not referenced:
                penalties.append({
                    "event_name": "unused_tool_result",
                    "dimension": ScoringDimension.tool_efficiency,
                    "evidence": (
                        f"Tool '{span.get('name', '')}' (span {span.get('span_id', '')}) "
                        f"produced output but no subsequent span references it."
                    ),
                    "trace_event_index": idx,
                })

        # Excessive tool calls: count > 2x rolling median
        median = historical_median if historical_median is not None else DEFAULT_MEDIAN_TOOL_CALLS
        if median > 0 and len(tool_call_spans) > 2 * median:
            penalties.append({
                "event_name": "excessive_tool_calls",
                "dimension": ScoringDimension.tool_efficiency,
                "evidence": (
                    f"Trace has {len(tool_call_spans)} tool calls, "
                    f"exceeding 2x the rolling median ({median:.0f})."
                ),
                "trace_event_index": None,
            })

        return penalties

    def score_tool_failures(self, spans: list[dict]) -> list[dict]:
        """Detect tool failure penalties from spans.

        Returns list of dicts with keys: event_name, evidence, trace_event_index.
        """
        penalties: list[dict] = []
        tool_call_spans = [s for s in spans if s.get("type") == "tool_call"]

        failed_spans: list[tuple[int, dict]] = []
        for idx, span in enumerate(tool_call_spans):
            status = span.get("status", "success")
            error = span.get("error")
            latency = int(span.get("latency_ms") or 0)

            is_error = status == "error" or (error and str(error).strip())
            is_timeout = latency > self.timeout_ms

            if is_error or is_timeout:
                failed_spans.append((idx, span))

            # Timeout detection
            if is_timeout:
                penalties.append({
                    "event_name": "tool_call_timeout",
                    "dimension": ScoringDimension.tool_failures,
                    "evidence": (
                        f"Tool '{span.get('name', '')}' (span {span.get('span_id', '')}) "
                        f"took {latency}ms, exceeding {self.timeout_ms}ms threshold."
                    ),
                    "trace_event_index": idx,
                })
            elif is_error:
                # Check for retry success
                key = _span_dedup_key(span)
                retried = False
                for later_idx, later_span in enumerate(tool_call_spans[idx + 1:], idx + 1):
                    if _span_dedup_key(later_span) == key:
                        later_status = later_span.get("status", "success")
                        if later_status != "error" and not later_span.get("error"):
                            retried = True
                            penalties.append({
                                "event_name": "tool_call_retry_success",
                                "dimension": ScoringDimension.tool_failures,
                                "evidence": (
                                    f"Tool '{span.get('name', '')}' failed at index {idx} "
                                    f"but succeeded on retry at index {later_idx}."
                                ),
                                "trace_event_index": idx,
                            })
                            break
                if not retried:
                    penalties.append({
                        "event_name": "tool_call_error",
                        "dimension": ScoringDimension.tool_failures,
                        "evidence": (
                            f"Tool '{span.get('name', '')}' (span {span.get('span_id', '')}) "
                            f"returned error: {str(error or status)[:200]}"
                        ),
                        "trace_event_index": idx,
                    })

        # Ignored tool failure: error span followed by non-tool span
        # (candidate for SLM confirmation)
        for idx, span in failed_spans:
            global_idx = spans.index(span) if span in spans else -1
            if global_idx < 0 or global_idx >= len(spans) - 1:
                continue
            next_span = spans[global_idx + 1]
            if next_span.get("type") != "tool_call":
                key = _span_dedup_key(span)
                # Check no retry anywhere later
                has_retry = any(
                    _span_dedup_key(s) == key
                    for s in tool_call_spans[tool_call_spans.index(span) + 1:]
                    if s is not span
                )
                if not has_retry:
                    penalties.append({
                        "event_name": "ignored_tool_failure",
                        "dimension": ScoringDimension.tool_failures,
                        "evidence": (
                            f"Tool '{span.get('name', '')}' failed at span {span.get('span_id', '')}, "
                            f"but agent continued with '{next_span.get('type', '')}' span without "
                            f"retry or acknowledgment. (SLM confirmation recommended)"
                        ),
                        "trace_event_index": idx,
                    })

        return penalties


def _span_dedup_key(span: dict) -> str:
    """Generate a dedup key from tool name + input params hash."""
    name = span.get("name", "")
    input_data = span.get("input") or ""
    if isinstance(input_data, dict):
        input_data = json.dumps(input_data, sort_keys=True)
    input_hash = hashlib.md5(str(input_data).encode()).hexdigest()
    return f"{name}:{input_hash}"
