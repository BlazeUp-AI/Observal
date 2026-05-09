# Agent Insights V2 — Roadmap

## Overview

Transform the insight system from "aggregate stats + single LLM call" into a full
**count, analyze per-session, narrate in parallel** pipeline with cost visibility,
regression detection, and qualitative session analysis.

---

## Phase 1: Cost Estimation & Enhanced Metrics

**Status: IN PROGRESS**

| Task | Status |
|------|--------|
| `services/insights/pricing.py` — model pricing, session cost, cost summary | Done |
| `metrics.py` — `get_per_session_tokens`, `get_tool_error_categories`, `get_interruption_metrics` | Done |
| `metrics.py` — `compute_all_metrics` returns `cost`, `tool_errors`, `interruptions` | Done |
| `narrative.py` — prompt includes cost/error/interruption data | Done |
| `web/src/lib/types.ts` — `InsightCostMetrics`, `InsightToolErrors`, `InsightInterruptions` | Done |
| `web/src/lib/api.ts` — insights API client methods | Done |
| `web/src/hooks/use-api.ts` — `useInsightReport`, `useInsightReports`, `useGenerateInsight` | Done |
| Report page — cost cards, cost-by-model table, error category chart | Done |
| Verify end-to-end: generate report, check cost metrics in JSON, frontend renders | Pending |

---

## Phase 2: Session Caching & 8+1 Parallel LLM Architecture

**Status: NOT STARTED**

| Task | Status |
|------|--------|
| Migration `0027_insight_v2_tables.py` — `insight_session_meta`, `insight_session_facets`, report columns | Pending |
| Model `insight_session_meta.py` | Pending |
| Model `insight_session_facets.py` | Pending |
| `services/insights/sections.py` — 8 section prompts + synthesis | Pending |
| `services/insights/anonymize.py` — user/cwd anonymization | Pending |
| `services/insights/session_cache.py` — PostgreSQL session meta cache | Pending |
| Rewrite `generator.py` — new orchestrator flow | Pending |
| Update `batch.py` — set `previous_report_id` | Pending |
| Update `models/insight_report.py` — `previous_report_id`, `aggregated_data`, `report_version` | Pending |
| `worker.py` — `job_timeout = 600` | Pending |
| `config.py` — `INSIGHT_FACET_MAX_CALLS`, `INSIGHT_FACET_CONCURRENCY`, `INSIGHT_SECTION_MODEL` | Pending |
| Frontend — V2 report rendering (8 sections + regression) | Pending |

---

## Phase 3: Per-Session Facet Extraction

**Status: NOT STARTED**

| Task | Status |
|------|--------|
| `services/insights/transcript.py` — build session transcript from otel_logs | Pending |
| `services/insights/facets.py` — LLM facet extraction with concurrency caps | Pending |
| Integrate facets into generator (after session metas) | Pending |
| Update `sections.py` — include aggregated facet data in DATA_BLOCK | Pending |

---

## Phase 4: Regression Detection & Report History

**Status: NOT STARTED**

| Task | Status |
|------|--------|
| `services/insights/regression.py` — threshold-based regression detection | Pending |
| Update `batch.py` — query previous completed report, set `previous_report_id` | Pending |
| Update `sections.py` — regression section with comparison data | Pending |
| Frontend — trend indicators on metric cards | Pending |

---

## Phase 5: Session Reconciliation Integration (#735)

**Status: NOT STARTED** (depends on #735 landing)

| Task | Status |
|------|--------|
| `services/insights/enrichment.py` — check for reconciled data, merge if available | Pending |
| Completeness scoring (0.0–1.0) | Pending |
| Cost code checks enriched fields first, falls back to aggregates | Pending |
| Facet extraction uses richer transcripts (thinking blocks) | Pending |

---

## Key Design Decisions

- **Cost computed in Python**, not SQL — keeps pricing table centralized and updatable
- **Per-session caching** in PostgreSQL — only new sessions cost ClickHouse queries or LLM calls
- **8+1 parallel section prompts** — better quality per section, amortized latency
- **Facet extraction capped at 100 sessions/run** — bounds LLM cost (~$0.40/run)
- **report_version field** — frontend renders V1 or V2 layout based on version
- **Phase 5 is additive** — all prior phases work without reconciled data

---

## Hard Limits

| Limit | Value |
|-------|-------|
| Max sessions analyzed per run | 500 |
| Max LLM facet extractions per run | 100 |
| Facet extraction concurrency | 25 |
| Worker job timeout | 600s |
| Min sessions to generate report | 5 |
| Regression threshold (error rate) | >10% increase |
| Regression threshold (cost) | >20% increase |
