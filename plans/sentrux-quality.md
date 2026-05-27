# Observal Code Quality Improvement Plan

## Current State

| Metric | Score | Raw | Notes |
|--------|-------|-----|-------|
| **Quality Signal** | **3,886** / 10,000 | — | Geometric mean of all 5 |
| Acyclicity | 1,111 🔴 | 8 cycles | **Bottleneck** — drags everything down |
| Modularity | 4,510 🟡 | 0.18 | 1,344 / 1,748 edges are cross-module |
| Depth | 5,000 🟡 | 8 levels | Acceptable for a monorepo |
| Equality | 5,070 🟡 | 0.49 | God files exist |
| Redundancy | 6,974 🟢 | 0.30 | Decent |

**Additional stats:**
- 852 files, 199K lines, 1,790 import edges
- 455 / 677 source files have **zero test coverage** (33% covered)
- 377 files with a single author (bus factor risk)
- 30 hotspot files (high churn × complexity)

## Why Bother Reaching 10K?

Reaching 10K isn't the point — the **trajectory** is. Here's what you concretely gain at each tier:

| Signal Range | What you get |
|---|---|
| **3,886 → 5,500** | AI agents stop hallucinating. Cycles broken = agents find the right file on first try. Less time fixing agent output. |
| **5,500 → 7,000** | Faster onboarding. New devs (and new AI sessions) understand the structure. PRs get smaller. Bugs localize to one module. |
| **7,000 → 8,500** | Fearless refactoring. Change one module, nothing else breaks. Deploy independently. CI is fast because tests are scoped. |
| **8,500 → 10,000** | Diminishing returns. Only worth it for safety-critical systems. |

**The practical payoff for Observal:** Your AI-assisted dev workflow (pi, Claude Code, etc.) will produce dramatically better output because the codebase is navigable. The agent can resolve imports unambiguously, find the right service, and avoid creating duplicates. You'll spend less time reviewing and fixing.

## Root Cause Diagnosis

### 1. Acyclicity (Score: 1,111) — THE problem

8 dependency cycles. Since sentrux uses geometric mean, this single metric at ~11% tanks the whole score. The cycles are likely:

- **web/src/hooks ↔ web/src/components** — hooks importing from components that import from hooks
- **observal-server/api ↔ observal-server/services** — routes importing services that lazily import route-layer stuff
- **observal_cli modules** — cmd_* files importing shared utilities that import back

The server uses deferred imports (`from services.X import Y` inside function bodies) which are fine at runtime but still create file-level edges in static analysis.

### 2. Modularity (Score: 4,510)

77% of imports cross module boundaries. The monorepo has 4 logical packages (`web`, `observal-server`, `observal_cli`, `ee`) but within each, the internal layering is flat. Everything imports everything.

### 3. Equality (Score: 5,070)

God files that concentrate too much:
- `web/src/hooks/use-api.ts` — 1,044 lines, single hook file for ALL API calls
- `web/src/lib/types.ts` — 973 lines, all types in one file
- `observal_cli/cmd_migrate.py` — 2,071 lines
- `observal_cli/cmd_ops.py` — 1,793 lines
- `ee/observal_server/routes/exec_dashboard.py` — 2,071 lines

## Approach

### Phase 1: Break Cycles (3,886 → ~6,000)

**Highest ROI.** Identify the 8 exact cycles and break them with:
- Extract shared types/interfaces to a `_types` or `_interfaces` module that both sides import from
- Move deferred imports to proper dependency direction
- Split circular hook/component relationships

### Phase 2: Split God Files (6,000 → ~7,000)

Break the top offenders:
- `use-api.ts` → domain-scoped hooks (`use-sessions-api.ts`, `use-agents-api.ts`, etc.)
- `types.ts` → co-locate types with their features
- `cmd_migrate.py` → extract subcommands into separate files
- `cmd_ops.py` → same

### Phase 3: Improve Modularity (7,000 → ~8,000)

- Define clear layer boundaries in `observal-server`: `models → services → api` (no backflow)
- Create `observal-server/services/interfaces/` for shared contracts
- In `web/src`, enforce: `lib → hooks → components → app` (no upward imports)

### Phase 4: Local Quality Checks

No CI enforcement or org-wide rules. Instead, devs run `sentrux` locally to check their work before pushing. The `.sentrux/rules.toml` is optional and personal — not committed.

## Files to Modify (Phase 1 — Cycles)

Need to identify exact files. Will require running sentrux Pro diagnostics or manual tracing of the 8 cycles.

Likely candidates:
- `web/src/hooks/use-api.ts`
- `web/src/hooks/use-role-guard.ts`
- `web/src/components/layouts/auth-guard.tsx`
- `web/src/components/layouts/role-guard.tsx`
- `observal-server/services/dynamic_settings.py`
- `observal-server/models/enterprise_config.py`

## Files to Modify (Phase 2 — God Files)

- `web/src/hooks/use-api.ts` → split into 5-6 domain files
- `web/src/lib/types.ts` → split into domain type files
- `observal_cli/cmd_migrate.py` → extract helpers
- `observal_cli/cmd_ops.py` → extract subcommands
- `ee/observal_server/routes/exec_dashboard.py` → decompose

## Verification

```bash
# After each commit, run locally:
sentrux                          # Check quality_signal improved

# Ensure nothing broke:
cd web && npm run build
cd observal-server && python -m pytest
cd observal_cli && python -m pytest
```

## Regression Safety

This refactoring is **purely structural** — no logic changes, no behavior changes:
- Moving code between files (same functions, same exports)
- Adjusting import paths to point to new locations
- Re-exporting from original locations for backwards compat where needed

Verification after each commit:
- `cd web && npm run build` (TypeScript catches any broken imports)
- `cd observal-server && python -m pytest` (tests catch any runtime issues)
- `cd observal_cli && python -m pytest`
- All existing tests must pass — no test modifications allowed

## Approach: One PR, Many Commits

Single branch `refactor/structural-quality`, one PR to main. Each commit is atomic and independently correct:

1. Commit: break cycle 1
2. Commit: break cycle 2
3. ...
4. Commit: split use-api.ts
5. Commit: split types.ts
6. etc.

This way you can review commit-by-commit but merge as one unit.

## Steps

- [ ] Manually trace and identify all 8 dependency cycles
- [ ] Break cycles one by one (one commit per cycle), re-scanning after each
- [ ] Split `use-api.ts` into domain hooks
- [ ] Split `types.ts` into co-located type files
- [ ] Split `cmd_migrate.py` and `cmd_ops.py`
- [ ] Clean up layering in `observal-server` (models → services → api, no backflow)
- [ ] Final `sentrux` scan to confirm score improvement
