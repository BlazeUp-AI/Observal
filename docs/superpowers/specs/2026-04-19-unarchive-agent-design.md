# Design: Unarchive Action for Archived Agents

**Issue:** #396
**Date:** 2026-04-19
**Status transition:** `archived` → `active` (direct restore, no re-review)

---

## Backend

### Endpoint: `PATCH /api/v1/agents/{agent_id}/unarchive`

**File:** `observal-server/api/routes/agent.py` (adjacent to existing `archive_agent` at line ~849)

- **Auth:** `require_role(UserRole.admin)` — same as archive
- **Org scoping:** same pattern as archive — if `current_user.org_id` is set, verify `agent.owner_org_id` matches
- **Status guard:** only `AgentStatus.archived` agents can be unarchived. Return 400 `"Agent is not archived"` otherwise.
- **Mutation:** `agent.status = AgentStatus.active`
- **Telemetry:** `emit_registry_event(action="agent.unarchive", ...)`
- **Response:** `{"id": str(agent.id), "name": agent.name, "status": agent.status.value}`

Pattern: exact mirror of `archive_agent`, changing status in the opposite direction.

---

## Web UI

### API client

**File:** `web/src/lib/api.ts`

Add `unarchive` method to the `registry` object, adjacent to existing `archive`:

```typescript
unarchive: (id: string) => patch(`/agents/${id}/unarchive`),
```

### React Query hook

**File:** `web/src/hooks/use-api.ts`

Add `useUnarchiveAgent()` mirroring `useArchiveAgent()`:

- **Mutation:** calls `registry.unarchive(id)`
- **onSuccess:** invalidates `["registry", "agents"]`, toast `"Agent restored"`
- **onError:** toast error message

### UI component

**File:** `web/src/app/(registry)/agents/page.tsx`

Add `UnarchiveAgentButton` component adjacent to `ArchiveAgentButton`:

- **Visibility:** admin only AND `agent.status === "archived"`
- **Icon:** `ArchiveRestore` from `lucide-react`
- **Styling:** `hover:text-green-600` (green, vs orange for archive)
- **Confirmation dialog:**
  - Title: "Restore Agent"
  - Body: "This will restore the agent to the public registry."
  - Confirm button: green variant, text "Restore" / "Restoring..."
  - Cancel button: outline variant

Render `UnarchiveAgentButton` in the same action slot as `ArchiveAgentButton` — they are mutually exclusive (archive shows for non-archived, unarchive shows for archived).

---

## CLI

### Command: `observal agent unarchive <agent_id>`

**File:** `observal_cli/cmd_agent.py`

Add new command mirroring the `agent_delete` (archive) command:

- **Argument:** `agent_id` — ID, name, row number, or @alias
- **Flag:** `--yes / -y` — skip confirmation
- **Confirmation prompt:** `Unarchive [bold]{item['name']}[/bold] ({resolved})?`
- **API call:** `client.patch(f"/api/v1/agents/{resolved}/unarchive")`
- **Success message:** `[green]✓ Agent restored[/green]`

---

## Playwright e2e test

### File: `web/e2e/unarchive-agent.spec.ts`

**Setup (uses API directly):**
1. Get admin access token via `getAccessToken()` / login API
2. Create an agent via `POST /api/v1/agents` (status=pending)
3. Approve it via `POST /api/v1/review/agents/{id}/approve` (status=active)
4. Archive it via `PATCH /api/v1/agents/{id}/archive` (status=archived)

**Test cases:**
1. **Archived agent shows unarchive button** — navigate to `/agents`, verify the archived agent has an ArchiveRestore button visible
2. **Unarchive restores agent** — click the unarchive button, confirm in dialog, verify toast "Agent restored", verify agent status returns to active
3. **Active agent does not show unarchive button** — verify the now-active agent has the archive button (not unarchive)

**Helpers:** uses existing `loginToWebUI(page)` and `waitForAPI()` from `e2e/helpers.ts`.

---

## Files changed

| File | Change |
|------|--------|
| `observal-server/api/routes/agent.py` | Add `unarchive_agent` endpoint |
| `web/src/lib/api.ts` | Add `unarchive` method |
| `web/src/hooks/use-api.ts` | Add `useUnarchiveAgent` hook |
| `web/src/app/(registry)/agents/page.tsx` | Add `UnarchiveAgentButton` component + render |
| `observal_cli/cmd_agent.py` | Add `agent_unarchive` command |
| `web/e2e/unarchive-agent.spec.ts` | New e2e test file |

## Not changing

- No database migration needed — `active` status already exists
- No new enum values
- No changes to agent model
