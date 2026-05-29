<!-- SPDX-FileCopyrightText: 2026 Hari Srinivasan <harisrini21@gmail.com> -->
<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Optic Logging Standardization Plan

## Context

The Observal codebase has ~130 files with logging. Currently, logs are shallow "function entered" breadcrumbs that don't help diagnose production issues. We need rich, descriptive logs that tell the story of what's happening, plus remote log streaming so hosted instances can be debugged without SSH.

**Inspiration: LiteLLM's approach**

LiteLLM uses stdlib `logging` with named loggers (`verbose_logger`, `verbose_proxy_logger`, `verbose_router_logger`). Their style:

- **Descriptive messages that explain what's happening**, not just function names:
  - `"Setting up GCP IAM authentication for Redis with service account."`
  - `"Anthropic /v1/messages: invalid thinking signature; stripping thinking blocks and retrying (attempt 2/3)."`
  - `"Both GCP IAM and Azure AD are configured for Redis. Using GCP IAM. Remove one to avoid misconfiguration."`
- **Errors include the full path** so you can grep: `"litellm.router_strategy.lowest_latency.py::async_log_success_event(): Exception occurred"`
- **Secret redaction is automatic** via a logging filter (not manual per-call)
- **JSON mode** for log aggregators, console mode for dev - switched by env var
- **f-strings used freely** (they chose readability over the loguru lazy-format micro-optimization)

**What we'll adopt:**
- Descriptive human-readable messages (not mechanical patterns)
- Module path in error messages for grep-ability
- Automatic secret redaction at the sink level (already have `secrets_redactor.py`)
- JSON mode for aggregators, colored for terminal, no-color flag for CLI

**What we'll keep different:**
- Loguru (optic) instead of stdlib - better TRACE support, better sink architecture
- Positional args (not f-strings) - project convention, zero-cost when level is disabled
- Ring buffer sink for SSE streaming - LiteLLM doesn't have this

## Approach

### Phase 1: Infrastructure (this commit batch)

1. **Ring buffer sink** - Bridge optic → ring buffer so SSE endpoint has data
2. **SSE endpoint** - `GET /api/v1/admin/logs/stream` with level/filter params
3. **CLI `--remote`** - `observal logs --remote` streams from hosted server
4. **Color policy** - Colors for terminal, no-color for aggregators, `--no-color` flag
5. **Increased ring buffer** - 2000 → 10000 entries (covers ~minutes under load)

### Phase 2: Rich instrumentation (batch by directory)

Rewrite logs to be descriptive. NOT mechanical "entered | elapsed" patterns. Instead:

```python
# BAD (mechanical, useless in prod):
optic.debug("resolve_agent: entered | agent_id={}, require_approved={}", agent_id, require_approved)

# GOOD (tells the story):
optic.debug("resolving agent components for '{}' (require_approved={})", agent.name, require_approved)
optic.trace("looking up {} component '{}' in DB", comp.component_type, comp.component_id)
optic.warning("component '{}' not approved (status: {}), skipping", listing.name, listing.status.value)
optic.debug("agent '{}' resolved: {} components, {} errors, {:.0f}ms", agent.name, len(components), len(errors), elapsed)
```

Directory batches:
- [ ] `services/clickhouse/` - query timing, row counts, error details
- [ ] `services/` core (session_ingest, redis, cache, events, dynamic_settings)
- [ ] `services/` auth (crypto, jwt_service, security_events)
- [ ] `services/` business (agent_resolver, model_resolver, alert_evaluator, webhook_delivery)
- [ ] `services/` generators (config_generator, hook_*, skill_*, sandbox_*)
- [ ] `services/ide/` - per-IDE config generation
- [ ] `api/routes/` - request handling, validation failures, response details
- [ ] `observal_cli/` - CLI commands, client HTTP calls

### Phase 3: Error quality

Every `except` block gets a log that answers:
- What were we trying to do?
- What went wrong?
- What's the impact? (request fails? degraded? retry?)
- What should the operator do?

```python
except Exception as e:
    optic.error(
        "failed to insert {} session events for session '{}': {} - "
        "events are lost, session will appear incomplete in the dashboard",
        len(rows), session_id, str(e)
    )
```

## Files to modify

### Phase 1 (infrastructure)
- `observal-server/services/optic.py` - add ring buffer sink
- `observal-server/services/log_buffer.py` - increase buffer size
- `observal-server/api/routes/logs_stream.py` - NEW: SSE endpoint
- `observal-server/main.py` - register new route
- `observal_cli/cmd_logs.py` - add `--remote` and `--no-color` flags
- `observal_cli/optic.py` - add `--trace` flag support

### Phase 2 (per directory, ~10 commits)
- All files under `observal-server/services/`
- All files under `observal-server/api/routes/`
- All files under `observal_cli/`

## Reuse

- `services/log_buffer.py` - existing ring buffer, just increase maxlen
- `services/secrets_redactor.py` - already have secret redaction, wire into sink
- `starlette.responses.StreamingResponse` - SSE without extra dependency
- `observal_cli/config.py` - existing server URL + token for --remote auth

## Steps

- [x] Unify all imports to `from loguru import logger as optic`
- [x] Remove stdlib logging / structlog from application code
- [ ] Add ring buffer sink to `services/optic.py`
- [ ] Increase ring buffer to 10000 entries
- [ ] Create SSE streaming endpoint
- [ ] Register route in main.py
- [ ] Update CLI `observal logs` with `--remote` and `--no-color`
- [ ] Update CLI `optic.py` with `--trace` flag
- [ ] Rewrite `services/clickhouse/` logs (descriptive style)
- [ ] Rewrite `services/` core logs
- [ ] Rewrite `services/` auth logs
- [ ] Rewrite `services/` business logic logs
- [ ] Rewrite `services/` generators logs
- [ ] Rewrite `api/routes/` logs
- [ ] Rewrite `observal_cli/` logs

## Verification

1. `python -m pytest tests/` passes
2. Start server locally, run `observal logs --remote --level DEBUG` in another terminal
3. Trigger an agent pull → verify rich log messages stream in real-time
4. Test with `--no-color` → verify no ANSI codes
5. Test error paths → verify error messages explain what happened and what to do
6. `grep -rn "logger\."` returns 0 hits in app code (only security_events.py exception)
