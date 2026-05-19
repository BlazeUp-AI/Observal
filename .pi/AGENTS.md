# Observal Agent Instructions

## Refactoring Philosophy

This codebase is undergoing a modularisation effort. The guiding rule is simple:

**Do not add to the pile. If you are touching a domain, modularise it.**

### What this means in practice

- **Don't extend if/elif chains** in `agent_config_generator.py`, `config_generator.py`, `cmd_scan.py`, or `cmd_doctor.py`. If you need to add or change IDE-specific logic, the answer is an IDE adapter module, not another branch.
- **Don't duplicate utilities.** `sanitize_name`, `is_already_shimmed`, `extract_mcp_servers`, `load_jsonc`, and hook marker detection already exist in multiple places. Don't add another copy. When you touch a file that has a duplicate, consolidate it.
- **Don't define IDE paths locally.** Config file paths, MCP server keys, hook types, and feature flags belong in the IDE_Registry (`schemas/ide_registry.py` and `observal_cli/ide_registry.py`). If you see a hardcoded path dict like `_IDE_PROJECT_CONFIGS`, delete it and derive from the registry instead.
- **Don't write parallel implementations.** `agent_builder.py` and `agent_config_generator.py` both generate IDE files. Changes to IDE output format must go in one place, not two.

### The target architecture

Component-first, with IDE-specific behaviour isolated behind adapters:

```
observal_cli/
  ide/        one adapter module per IDE, implements IDE_Protocol
  config/     config generation orchestrator
  scanning/   scanner aggregator
  hooks/      hook spec interface + per-IDE specs
  sessions/   JSONL session parsers (Claude Code, Kiro)
  telemetry/  shim, proxy, buffer, OTLP helpers
  skills/     skill file generator
  shared/     IDE_Registry, shared utilities, cross-cutting types
```

Adding a new IDE means adding one file in `ide/` and one entry in the registry. Nothing else should need to change.

### Migration phases (current state)

- **Phase 1** (shared utilities): not started
- **Phase 2** (IDE_Protocol + adapter stubs): not started
- **Phase 3** (config generation to adapters): not started
- **Phase 4** (scanning to adapters): not started
- **Phase 5** (agent_builder + config_generator unification, sessions/ domain): not started
- **Phase 6** (directory restructure, `docs/adding-an-ide.md`): not started

Server-side splits (independent of IDE phases):
- **S1** (ClickHouse: split 1293-line monolith into client/schema/insert/query): not started
- **S2** (Worker: split 6 job types into `jobs/` directory): not started
- **S3** (Agent routes: split 1779-line `agent.py` into crud/install/manifest/validate): not started

### ee/ boundary

The `ee/` directory is enterprise-only. The open-source core must never import from `ee/` directly.

- Enterprise features are accessed through loader modules in `services/` (e.g. `services/insights/__init__.py`) that gate on availability flags.
- Tests in `observal-server/tests/` and `tests/` must not import from `ee/` directly. Use `pytest.importorskip` or move ee-specific tests into `ee/` itself.
- `worker.py` and route files must go through `services/` loaders, never `from ee.something import ...`.

### Hard rewrite policy

No deprecation wrappers, no re-export shims. When code moves, callers are updated in the same PR and the old location is deleted. Dead code is removed immediately.
