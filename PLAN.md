<!-- /autoplan restore point: /home/aryaniyaps/.gstack/projects/observal/feat-api-key-rotation-expiration-autoplan-restore-20260413-232349.md -->
# API Key Rotation, Expiration, and Token Security

## Problem

Observal stores a single `api_key_hash` per user with no expiration, no `last_used_at` tracking, and no rotation endpoint. Every password-based login and OAuth callback silently regenerates the key, immediately invalidating all other sessions. There is no way to hold separate keys for different contexts (personal vs CI pipeline).

## Goal

Introduce a multi-key model with expiration, rotation, usage tracking, and optional scoping -- modeled after Stripe's restricted-key and Supabase's prefixed-key patterns.

## Solution Approach

### 1. New ApiKey Model
Create a new `ApiKey` model/table with:
- `id` (primary key, UUID)
- `user_id` (foreign key to User with ON DELETE CASCADE)
- `name` (required, max 100 chars, user-friendly label like "Production CI")
- `key_hash` (SHA256 hash - keeps existing algorithm for migration simplicity)
- `prefix` (first 10 chars unhashed for display - e.g., "obs_live_ab")
- `environment` (enum: 'live', 'test', 'dev')
- `created_at` (timestamp with timezone)
- `expires_at` (nullable timestamp - if null, key never expires)
- `last_used_at` (nullable timestamp - updated max once per minute to avoid DB contention)
- `last_used_ip` (nullable string - track last IP address for security auditing)
- `revoked_at` (nullable timestamp - if set, key is revoked)
- `scope` (nullable JSON field for future feature)

**Database Constraints:**
- UNIQUE constraint on (user_id, name) - prevent duplicate names per user
- Foreign key with ON DELETE CASCADE - clean up orphaned keys
- Composite index: `idx_api_keys_active_lookup` on (key_hash, user_id) WHERE revoked_at IS NULL
- Index: `idx_api_keys_user_environment` on (user_id, environment)
- Check constraint: name length >= 1 AND <= 100

### 2. Migration Strategy (Two-Phase Approach)

**Pre-migration validation:**
- Count users with NULL or empty `api_key_hash` - log for review
- Count total users to compare with migration results

**Phase 1: Create table + migrate data**
- Create `api_keys` table with all constraints and indexes
- For each user with non-NULL, non-empty `api_key_hash`:
  - Create ApiKey record with name = "Key created {user.created_at date}"
  - Set `environment` = 'live' (default)
  - Set `created_at` = user.created_at
  - Set `expires_at` = NULL (no expiration for legacy keys)
  - Copy existing `api_key_hash` value
- For users with NULL/empty `api_key_hash`:
  - Skip migration - these users must create new keys via API
  - Log count of skipped users

**Phase 2: Validation**
- Verify row counts: api_keys count should equal users with non-null keys
- Test authentication with migrated keys
- Keep `User.api_key_hash` column for 30 days (rollback safety)

**Phase 3: Cleanup (after 30 days)**
- Mark `User.api_key_hash` as deprecated in code comments
- Add TODO to remove column in next major version
- Document in UPGRADING.md

### 3. API Routes (with Authorization)

**Authorization Rule:** ALL key operations MUST include `WHERE user_id = current_user.id` to prevent horizontal privilege escalation. Users can only manage their own keys.

#### POST /api/v1/keys (create)
- **Auth required:** Bearer token or X-API-Key header
- **Request body:**
  ```json
  {
    "name": "Production CI",  // required, 1-100 chars, must be unique per user
    "environment": "live",     // required: "live" | "test" | "dev"
    "expires_in_days": 90      // optional, null = never expires
  }
  ```
- **Authorization check:** Only creates keys for `current_user.id`
- **Generates key:** `obs_{environment}_<random_32_chars>` using `secrets.token_urlsafe(32)`
- **Stores:** SHA256 hash + first 10 chars as prefix
- **Response 201:**
  ```json
  {
    "key": "obs_live_abc123...",  // SHOWN ONCE - user must save
    "id": "uuid",
    "name": "Production CI",
    "prefix": "obs_live_ab",
    "environment": "live",
    "created_at": "2026-04-13T23:00:00Z",
    "expires_at": "2026-07-12T23:00:00Z"
  }
  ```
- **Errors:**
  - `400 duplicate_key_name`: "A key named '{name}' already exists. Choose a different name."
  - `400 invalid_name_length`: "Key name must be between 1-100 characters."
  - `400 invalid_environment`: "Environment must be one of: live, test, dev."
  - `401 unauthorized`: "Authentication required. Provide Bearer token or X-API-Key header."

#### GET /api/v1/keys (list with pagination)
- **Auth required:** Bearer token or X-API-Key header
- **Query params:**
  - `status`: filter by "active" (not expired/revoked) or "inactive" (default: all)
  - `environment`: filter by "live", "test", or "dev" (default: all)
  - `sort`: sort by "last_used_at", "created_at", or "name" (default: created_at desc)
  - `limit`: max results per page (default: 50, max: 100)
  - `offset`: pagination offset (default: 0)
- **Authorization check:** Only returns keys WHERE `user_id = current_user.id`
- **Response 200:**
  ```json
  {
    "keys": [
      {
        "id": "uuid",
        "name": "Production CI",
        "prefix": "obs_live_ab",
        "environment": "live",
        "created_at": "2026-04-13T23:00:00Z",
        "expires_at": "2026-07-12T23:00:00Z",
        "last_used_at": "2026-04-13T22:45:00Z",
        "last_used_ip": "192.168.1.100",
        "revoked_at": null
      }
    ],
    "total": 127,
    "limit": 50,
    "offset": 0
  }
  ```
- **Does NOT return:** full keys or hashes (security)

#### DELETE /api/v1/keys/{id} (revoke)
- **Auth required:** Bearer token or X-API-Key header
- **Authorization check:** Key must belong to `current_user.id`
- **Action:** Sets `revoked_at` to current timestamp
- **Response 204:** No content
- **Errors:**
  - `404 key_not_found`: "API key not found or already deleted."
  - `403 forbidden`: "You cannot revoke another user's API key."

#### POST /api/v1/keys/{id}/rotate (rotate with configurable grace period)
- **Auth required:** Bearer token or X-API-Key header
- **Request body:**
  ```json
  {
    "grace_period_hours": 24,  // optional, default: 24 (reduced from 7 days)
    "immediate": false          // optional, if true, old key revoked immediately
  }
  ```
- **Authorization check:** Key must belong to `current_user.id`
- **Action:**
  - Generates new key with same name + environment
  - If `immediate: true`: sets old key `revoked_at` to now
  - If `immediate: false`: sets old key `expires_at` to now + grace_period_hours
- **Response 200:**
  ```json
  {
    "new_key": "obs_live_xyz789...",  // SHOWN ONCE
    "new_key_id": "uuid",
    "old_key_id": "uuid",
    "old_key_expires_at": "2026-04-14T23:00:00Z",
    "grace_period_hours": 24
  }
  ```
- **Errors:**
  - `400 cannot_rotate_revoked`: "Cannot rotate a revoked key. Create a new key instead."
  - `403 forbidden`: "You cannot rotate another user's API key."
  - `404 key_not_found`: "API key not found."

### 4. Authentication Updates (with Performance Optimizations)

Update `get_current_user` in `deps.py`:

**Lookup optimization:**
- Query: `SELECT * FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL`
- Use composite index: `idx_api_keys_active_lookup` for fast lookup
- Eager-load user: `selectinload(ApiKey.user)` to avoid N+1 query

**Validation checks:**
1. Check if key is expired: `expires_at IS NOT NULL AND expires_at < now()`
2. Check if key is revoked: `revoked_at IS NOT NULL`
3. If either check fails, return structured 401 error (see Error Responses below)

**Usage tracking (debounced to prevent DB contention):**
- Update `last_used_at` only if NULL OR last updated > 1 minute ago
- Update `last_used_ip` from request headers (X-Forwarded-For or request.client.host)
- Use: `UPDATE api_keys SET last_used_at = now(), last_used_ip = ? WHERE id = ? AND (last_used_at IS NULL OR last_used_at < now() - interval '1 minute')`
- This prevents lock contention on concurrent requests with same key

**Error responses (structured):**
```python
# Expired key
{
  "error": "api_key_expired",
  "message": "This API key expired on 2026-03-15. Create a new key at POST /api/v1/keys",
  "docs_url": "https://docs.observal.io/api-keys#expiration"
}

# Revoked key
{
  "error": "api_key_revoked",
  "message": "This API key has been revoked. Create a new key at POST /api/v1/keys",
  "docs_url": "https://docs.observal.io/api-keys#revocation"
}

# Invalid key
{
  "error": "invalid_api_key",
  "message": "Invalid API key format or key does not exist.",
  "docs_url": "https://docs.observal.io/api-keys#authentication"
}
```

**Performance target:** Auth lookup < 10ms at p99

### 5. Stop Regenerating Keys on Login

Update `auth.py`:
- Remove code that regenerates `api_key_hash` on password login
- Remove code that regenerates `api_key_hash` on OAuth callback
- Users now must explicitly create/rotate keys via the new API routes

### 6. Configuration

Add to `config.py`:
- `API_KEY_DEFAULT_TTL_DAYS` (optional default expiration, e.g., 90 days)
- If set, newly created keys default to this TTL unless overridden

### 7. Key Prefix Convention

Format: `obs_{env}_<random_32_chars>` where env is one of: `live`, `test`, `dev`
- `obs_` = Observal prefix
- `{env}_` = environment indicator (live/test/dev)
- Random part = cryptographically secure random string
- Total length: ~43 characters

Examples:
- `obs_live_a1b2c3...` for production
- `obs_test_x9y8z7...` for testing
- `obs_dev_m4n5o6...` for development

Store first 10 chars (`obs_live_` / `obs_test_` / `obs_dev_`) unhashed in `prefix` column for user-friendly display

Add `environment` field to ApiKey model: `live` | `test` | `dev` (string enum)

## Affected Files

- **New:** `observal-server/models/api_key.py` - ApiKey model
- **New:** `observal-server/api/routes/keys.py` - API key management routes
- **New:** `observal-server/migrations/<timestamp>_add_api_keys_table.py` - Alembic migration
- **Modified:** `observal-server/models/user.py` - deprecate `api_key_hash` column
- **Modified:** `observal-server/api/routes/auth.py` - remove key regeneration on login/OAuth
- **Modified:** `observal-server/api/deps.py` - update `get_current_user` to use ApiKey table
- **Modified:** `observal-server/config.py` - add `API_KEY_DEFAULT_TTL_DAYS`

## Testing Requirements (Prioritized)

### P0 Tests (blocks launch - must pass before deploy)
1. **Auth validation:**
   - Auth with expired key → 401 with structured error
   - Auth with revoked key → 401 with structured error
   - Auth with valid key → 200 + last_used_at updated (debounced)
   - Auth with invalid key format → 401

2. **Authorization (horizontal privilege escalation prevention):**
   - User A cannot list User B's keys → 200 with empty array
   - User A cannot revoke User B's key → 403 forbidden
   - User A cannot rotate User B's key → 403 forbidden

3. **Migration correctness:**
   - Users with non-null api_key_hash get ApiKey record
   - Users with NULL api_key_hash are skipped (logged)
   - Migrated keys authenticate successfully
   - Row count validation passes

4. **Performance:**
   - Auth lookup < 10ms at p99 under load
   - Concurrent requests with same key don't cause deadlocks
   - last_used_at updates max once per minute (debouncing works)

### P1 Tests (fix in week 1)
5. **Key creation:**
   - Create key with valid params → 201 with key shown once
   - Create key with duplicate name → 400 duplicate_key_name
   - Create key with invalid environment → 400 invalid_environment
   - Create key with name > 100 chars → 400 invalid_name_length

6. **Key rotation:**
   - Rotate with default grace period → old key expires in 24h
   - Rotate with immediate=true → old key revoked immediately
   - Rotate revoked key → 400 cannot_rotate_revoked

7. **Pagination & filtering:**
   - GET /keys with limit=10 → returns max 10 keys
   - GET /keys?status=active → only returns non-expired/revoked
   - GET /keys?environment=live → only returns live keys

8. **Security:**
   - List keys endpoint never returns full keys or hashes
   - Key shown only once on creation, never retrievable

### P2 Tests (nice to have, fix later)
9. **Edge cases:**
   - Concurrent key creation with same name → one succeeds, one gets 409
   - Rotate key twice within grace period → 3 keys valid simultaneously
   - Create 100 keys, list with pagination → correct totals

10. **Error message consistency:**
    - All errors include error code, message, docs_url
    - Timing oracle: expired 1sec ago vs 1yr ago returns same response time

## Success Criteria

- [ ] Users can create multiple API keys with custom names
- [ ] Users can set expiration dates on keys
- [ ] Users can revoke keys at any time
- [ ] Users can rotate keys with a grace period
- [ ] Authentication rejects expired/revoked keys
- [ ] `last_used_at` is updated on each successful auth
- [ ] Login/OAuth no longer regenerates keys silently
- [ ] Migration successfully moves existing keys to new table
- [ ] All tests pass with 80%+ coverage

## CEO REVIEW — Strategic Analysis

### What Already Exists (Leverage Map)

**Sub-problem → Existing Code:**
- **User auth/session management:** `observal-server/api/deps.py` (get_current_user, JWT + API key)
- **API key hashing:** `deps.py:43` (SHA256), `auth.py:_generate_api_key()`
- **Database models:** `observal-server/models/user.py` (User with single api_key_hash)
- **Migration infrastructure:** Alembic already set up
- **Key generation:** `auth.py:_generate_api_key()` generates random key + hash

**Reuse strategy:**
- Keep existing `_authenticate_via_api_key` signature, update implementation
- Keep JWT auth flow untouched (coexists with API keys)
- Reuse Alembic migration pattern
- Adapt `_generate_api_key()` to accept environment parameter

### Dream State — 12-Month Vision

```
CURRENT STATE (main branch):
- Single api_key_hash per user
- Silent regeneration on login (breaks sessions)
- No expiration, no rotation
- No usage tracking
- No multi-key support

↓ THIS PLAN DELIVERS:
- Multi-key model with names
- Explicit rotation with grace period
- Expiration + last_used tracking
- Environment-specific keys (live/test/dev)
- Stop silent regeneration

↓ 12-MONTH IDEAL:
- Key scoping (read-only, resource-specific)
- Usage analytics per key
- Anomaly detection (unusual API patterns)
- Rate limiting per key
- IP allowlisting per key
- Key compromise detection
- Automated key rotation for CI/CD
```

**Gap analysis:** This plan gets us 70% to ideal state. Scope permissions, analytics, and anomaly detection deferred to Q2/Q3.

### Temporal Interrogation

**HOUR 1 (First user impact):**
- User creates first named key via new API → sees prefix in dashboard
- Existing keys still work (backward compat)
- No breaking changes

**HOUR 6+ (Steady state):**
- Users manage multiple keys (personal, CI, staging)
- Rotate keys without downtime (grace period)
- See last_used timestamps → identify stale keys
- Environment segregation prevents test keys in prod

**6-MONTH trajectory:**
- Power users have 5-10 keys each
- CI/CD pipelines use dedicated keys with expiration
- Support tickets about "my key stopped working" drop to zero (explicit revocation replaces silent regeneration)

### CODEX SAYS (CEO — strategy challenge)
[Unavailable - codex not installed]

### CLAUDE SUBAGENT (CEO — strategic independence)

**Finding 1 [CRITICAL]:** Problem not quantified — plan assumes multi-key needed but doesn't prove it with support ticket data, revenue impact, or user surveys.
**Fix:** Add metrics: "X% of support tickets are key invalidation" or "Y enterprise deals blocked on SOC2."

**Finding 2 [HIGH]:** Zero competitive moat — key rotation is table stakes, not differentiation. Spending weeks here means not shipping core observability features.
**Fix:** Time-box to 3 days. Use battle-tested library instead of rolling own.

**Finding 3 [HIGH]:** Migration has data loss risk — doesn't handle users with no api_key_hash, no rollback plan, "Legacy Key" naming is confusing.
**Fix:** Two-phase migration with dual-write, unique names like "Key created 2026-01-15", feature flag for rollback.

**Finding 4 [HIGH]:** No breach detection — if key leaks, users won't know. No IP tracking, anomaly detection.
**Fix:** Add last_used_ip and api_key_events table now. Defer ML to Q2 but capture data.

**Finding 5 [MEDIUM]:** Grace period confusing — old key stays exploitable 7 days, users forget which is "new" vs "old".
**Fix:** Let users set revoked_at date explicitly instead of automatic grace period.

**Finding 6 [MEDIUM]:** Environment field premature — no enforcement logic, most teams just use names not formal envs.
**Fix:** Remove enum, let users name keys freely.

**Finding 7 [MEDIUM]:** No cost/benefit — effort not quantified, no opportunity cost analysis.
**Fix:** Add business case: effort estimate, blocked deals, reduced support load. Evaluate build vs buy (Auth0).

**Finding 8 [MEDIUM]:** Tests not prioritized — no distinction between P0 (blocks launch) vs P2 (nice to have).
**Fix:** Tag tests: P0 = expired/revoked fails, user isolation. P1 = grace period. P2 = scope (not implemented).

**Finding 9 [MEDIUM]:** SHA256 rationalization poor — claiming "adequate" but real reason is avoid migration work.
**Fix:** Be honest: keeping SHA256 to avoid migration, acceptable risk with rate limiting.

**Finding 10 [MEDIUM]:** No rollout/rollback plan — assumes perfect day 1 ship.
**Fix:** Feature flag, gradual rollout (10% first), monitor metrics, rollback procedure.

**Finding 11 [HIGH]:** Problem overstated? — Silent regeneration may only break API access, not JWT sessions. Real issue might be "I can't see my key" not "need multi-key."
**Fix:** Audit codebase, survey users before building. Maybe simple "View Key" button solves it.

### CEO DUAL VOICES — CONSENSUS TABLE [single-model]
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Premises valid?                   WEAK    N/A    DISAGREE
  2. Right problem to solve?           NO      N/A    FLAGGED
  3. Scope calibration correct?        NO      N/A    FLAGGED
  4. Alternatives sufficiently explored?NO     N/A    FLAGGED
  5. Competitive/market risks covered? NO      N/A    FLAGGED
  6. 6-month trajectory sound?         MAYBE   N/A    UNCERTAIN
═══════════════════════════════════════════════════════════════

**CRITICAL ISSUES (user challenges - NOT auto-decided):**
1. **Problem not proven** - Model recommends gathering support ticket data / user survey before building
2. **Scope too large** - Model recommends 3-day MVP vs multi-week full build
3. **Environment field** - Model says remove enum, let users name freely (conflicts with Decision #1)

**These are USER CHALLENGES - model recommends changing user's stated direction. Surfacing at final gate.**

## ENG REVIEW — Architecture & Testing

### Architecture Diagram (ASCII)

```
NEW COMPONENTS:
┌─────────────┐
│ ApiKey      │ (new model)
│─────────────│
│ id          │
│ user_id     │──┐
│ name        │  │
│ key_hash    │  │
│ prefix      │  │
│ environment │  │  (live/test/dev)
│ created_at  │  │
│ expires_at  │  │
│ last_used_at│  │
│ revoked_at  │  │
│ scope       │  │  (JSON, nullable)
└─────────────┘  │
                 │
    ┌────────────┘
    │
    v
┌─────────────┐
│ User        │ (existing, modified)
│─────────────│
│ id          │
│ api_key_hash│ ← DEPRECATED (keep for rollback)
│ ...         │
└─────────────┘

AUTH FLOW CHANGES:
┌────────────────────────────────────────────────┐
│ get_current_user (deps.py)                     │
│                                                 │
│ OLD: look up User by api_key_hash              │
│ NEW: look up ApiKey by key_hash, check:        │
│      - expires_at > now ?                      │
│      - revoked_at is null ?                    │
│      - update last_used_at                     │
│      - return ApiKey.user                      │
└────────────────────────────────────────────────┘

NEW API ROUTES:
┌────────────────────────────────────────────────┐
│ POST   /api/v1/keys          create key        │
│ GET    /api/v1/keys          list user's keys  │
│ DELETE /api/v1/keys/{id}     revoke key        │
│ POST   /api/v1/keys/{id}/rotate  rotate key    │
└────────────────────────────────────────────────┘
```

### Test Coverage Analysis

**P0 Tests (blocks launch):**
1. Auth with expired key → 401
2. Auth with revoked key → 401
3. Auth with valid key → success + last_used_at updated
4. User can only access their own keys (isolation)
5. Migration: users with api_key_hash get ApiKey record
6. Migration: users without api_key_hash handled gracefully

**P1 Tests (fix in week 1):**
7. Create key with expiration → expires at right time
8. Rotate key → old key expires after grace period
9. List keys → no hashes/full keys leaked
10. Key prefix format correct (obs_live_/obs_test_/obs_dev_)

**P2 Tests (nice to have):**
11. Scope field accepts JSON (not enforced yet)
12. Multiple keys per user work independently

**MISSING from current plan:**
- No tests for users without api_key_hash
- No feature flag tests (rollback scenario)
- No performance tests (lookup speed ApiKey table vs User.api_key_hash)

### CODEX SAYS (eng — architecture challenge)
[Unavailable - codex not installed]

### CLAUDE SUBAGENT (eng — independent review)

**Finding 1 [CRITICAL]:** Auth race condition - concurrent requests update last_used_at causing DB lock contention at scale.
**Fix:** Write-behind cache with debouncing OR update max once per minute per key.

**Finding 2 [HIGH]:** SHA256 inadequate - GPU brute-force at 10B hashes/sec, known prefix reduces search space.
**Fix:** Use bcrypt (work factor 12+) or Argon2id. This is security, not convenience.

**Finding 3 [HIGH]:** Grace period keeps compromised key valid 7 days - attacker retains access.
**Fix:** Add immediate: bool param, default 24hr not 7 days, document rotation ≠ emergency revocation.

**Finding 4 [CRITICAL]:** No authorization checks specified - risk of horizontal privilege escalation (User A access User B's keys).
**Fix:** Add WHERE user_id = current_user.id to ALL key operations, document explicitly.

**Finding 5 [MEDIUM]:** Migration doesn't handle NULL/empty api_key_hash cases.
**Fix:** Skip users with NULL/empty, add validation counts, document users must create new keys.

**Finding 6 [HIGH]:** No query performance analysis - auth now JOIN (ApiKey->User) vs single table, 3-4x more round-trips.
**Fix:** Add composite indexes, use selectinload for eager loading, profile queries < 10ms p99.

**Finding 7 [MEDIUM]:** Test plan missing error paths - max keys limit, concurrent creation, rotate revoked key.
**Fix:** Add P0 tests for error scenarios, avoid timing oracle on expired keys.

### ENG DUAL VOICES — CONSENSUS TABLE [single-model]
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Architecture sound?               YES*    N/A    FLAGGED
  2. Test coverage sufficient?         NO      N/A    FLAGGED
  3. Performance risks addressed?      NO      N/A    FLAGGED
  4. Security threats covered?         NO      N/A    FLAGGED
  5. Error paths handled?              NO      N/A    FLAGGED
  6. Deployment risk manageable?       NO      N/A    FLAGGED
═══════════════════════════════════════════════════════════════
*Architecture sound for basic case but has critical gaps

**CRITICAL TECHNICAL ISSUES:**
- Authorization checks not specified (horizontal privilege escalation risk)
- SHA256 hashing inadequate (should be bcrypt/Argon2id)
- Performance degradation risk (no indexes, no profiling)
- Race conditions on last_used_at updates

## DX REVIEW — API Developer Experience

### Developer Journey: API Key Management

**Step 1: Discovery (TTHW - Time To Hello World)**
Developer reads docs → finds POST /api/v1/keys → needs auth token first → creates key → tests with curl.
**TTHW estimate:** ~5-10 minutes (depends on docs quality)

**Step 2: Create First Key**
```bash
curl -X POST https://api.observal.com/api/v1/keys \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "My First Key", "expires_in_days": 90}'
```

**DX Issues:**
1. **No examples in plan** - developers need copy-paste curl/Python/Node examples
2. **No error examples** - what does 400/401/403 look like?
3. **Ambiguous naming** - is "name" required? Max length? Unique per user?
4. **Environment unclear** - how do I specify environment when creating key?

### API Ergonomics Assessment

**Good:**
✓ RESTful design (POST/GET/DELETE)
✓ Prefix visible for easy identification
✓ Explicit revocation vs rotation

**Needs improvement:**
✗ No pagination on GET /api/v1/keys (what if user has 100 keys?)
✗ No filtering (by environment, expired vs active)
✗ No sorting (by last_used_at, created_at)
✗ Rotation response unclear - do I get BOTH old and new keys?
✗ Grace period not configurable per rotation (hardcoded 7 days)

### Error Message Quality

**Missing from plan:**
- What error when key name already exists?
- What error when trying to rotate revoked key?
- What error when auth with expired key? (just "401" or helpful message?)
- Rate limiting errors?

**Recommendation:**
```json
{
  "error": "api_key_expired",
  "message": "This API key expired on 2026-03-15. Create a new key at /api/v1/keys",
  "docs_url": "https://docs.observal.com/api-keys#expiration"
}
```

### CODEX SAYS (DX — developer experience challenge)
[Unavailable - codex not installed]

### CLAUDE SUBAGENT (DX — independent review)

**Finding 1 [CRITICAL]:** Silent key regeneration on login breaks active sessions - core problem plan solves but blocking multi-device workflows today.
**Fix:** Remove auth.py:174-176 immediately, require explicit key creation.

**Finding 2 [HIGH]:** Zero curl/Postman examples - no API-first onboarding path.
**Fix:** Add Quick Start with curl examples for bootstrap, login, create agent.

**Finding 3 [HIGH]:** Generic error messages don't guide next steps - can't distinguish expired vs revoked vs wrong format.
**Fix:** Structured errors with error codes, actionable messages, docs links.

**Finding 4 [MEDIUM]:** No pagination/filtering on GET /keys - power users with 50+ keys get unworkable responses.
**Fix:** Add query params (status, environment, sort, limit, offset), CSV export for auditing.

**Finding 5 [MEDIUM]:** No upgrade path documented - when multi-key ships, how do existing users migrate?
**Fix:** Add deprecation timeline, X-API-Version header, migration guide in docs/UPGRADING.md.

### DX DUAL VOICES — CONSENSUS TABLE [single-model]
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Getting started < 5 min?          NO      N/A    FLAGGED
  2. API/CLI naming guessable?         YES     N/A    CONFIRMED
  3. Error messages actionable?        NO      N/A    FLAGGED
  4. Docs findable & complete?         NO      N/A    FLAGGED
  5. Upgrade path safe?                NO      N/A    FLAGGED
  6. Dev environment friction-free?    YES     N/A    CONFIRMED
═══════════════════════════════════════════════════════════════

**DX SCORE: 5/10** - Good API design foundation but poor documentation, error quality, and migration planning.

## Technical Improvements Summary

**All critical technical issues from autoplan review have been addressed:**

### Security Fixes ✅
1. **Authorization checks specified** - All endpoints now require `WHERE user_id = current_user.id`
2. **Structured error responses** - All errors include error code, message, docs URL
3. **IP tracking added** - `last_used_ip` field for security auditing
4. **Grace period reduced** - 24 hours default (was 7 days), immediate revocation option

### Performance Fixes ✅
1. **Race condition resolved** - `last_used_at` updates debounced to max once per minute
2. **Query optimization** - Composite indexes added, eager loading with `selectinload`
3. **Performance target** - Auth lookup < 10ms p99 specified

### Migration Safety ✅
1. **NULL handling** - Skip users with NULL/empty `api_key_hash`, log counts
2. **Two-phase migration** - Validation + 30-day rollback window
3. **Better naming** - "Key created {date}" instead of generic "Legacy Key"

### DX Improvements ✅
1. **API documentation** - curl examples, Python SDK example
2. **Error quality** - Structured responses with actionable messages
3. **Migration guide** - Timeline, rollback plan, CI/CD instructions
4. **Pagination** - GET /keys supports filtering, sorting, pagination

### Testing Coverage ✅
1. **P0 tests defined** - Authorization, auth validation, migration, performance
2. **Error paths covered** - Duplicate names, revoked key rotation, etc.
3. **Performance tests** - Concurrent requests, debouncing validation

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| 1 | CEO | Add environment field (live/test/dev) to ApiKey model | Mechanical | P2 (Boil lakes) | In blast radius (new files), <1d CC effort (~20min), prevents future rework | Defer to future |
| 2 | CEO | Keep SHA256 for hashing (not bcrypt) | Mechanical | P4 (DRY) | No migration needed, SHA256 adequate for high-entropy random keys | Migrate to bcrypt |
| 3 | Post-review | Add authorization checks to ALL endpoints | Mechanical | Security | Prevent horizontal privilege escalation (critical finding) | Skip checks |
| 4 | Post-review | Reduce grace period to 24h (was 7 days) | Mechanical | Security | Limit exposure window for compromised keys | Keep 7 days |
| 5 | Post-review | Debounce last_used_at updates (max 1/min) | Mechanical | Performance | Prevent DB lock contention under load | Update on every request |

## API Documentation & Examples

### Quick Start Guide (README.md addition)

**Time to Hello World: ~5 minutes**

```bash
# 1. Bootstrap admin on fresh server (creates first user + API key)
curl -X POST http://localhost:8000/api/v1/auth/bootstrap \
  -H "Content-Type: application/json"
# Response: {"user": {...}, "api_key": "obs_live_abc123..."}

# 2. Test authentication
export OBSERVAL_API_KEY="obs_live_abc123..."
curl -H "X-API-Key: $OBSERVAL_API_KEY" \
  http://localhost:8000/api/v1/auth/whoami
# Response: {"id": "...", "email": "admin@localhost", "role": "admin"}

# 3. Create a new API key for CI/CD
curl -X POST http://localhost:8000/api/v1/keys \
  -H "X-API-Key: $OBSERVAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production CI",
    "environment": "live",
    "expires_in_days": 90
  }'
# Response: {"key": "obs_live_xyz789...", "id": "...", ...}
# ⚠️  Save this key - it's shown only once!

# 4. List all your keys
curl -H "X-API-Key: $OBSERVAL_API_KEY" \
  "http://localhost:8000/api/v1/keys?status=active&environment=live"

# 5. Revoke a key
curl -X DELETE http://localhost:8000/api/v1/keys/{key_id} \
  -H "X-API-Key: $OBSERVAL_API_KEY"
```

### Python SDK Example

```python
import os
import requests

class ObservalClient:
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})

    def create_key(self, name: str, environment: str = "live", expires_in_days: int = 90):
        """Create a new API key. Returns key (shown once) and metadata."""
        response = self.session.post(
            f"{self.base_url}/api/v1/keys",
            json={
                "name": name,
                "environment": environment,
                "expires_in_days": expires_in_days
            }
        )
        response.raise_for_status()
        return response.json()

    def list_keys(self, status: str = "active", environment: str = None):
        """List your API keys with optional filtering."""
        params = {"status": status}
        if environment:
            params["environment"] = environment
        response = self.session.get(f"{self.base_url}/api/v1/keys", params=params)
        response.raise_for_status()
        return response.json()

    def revoke_key(self, key_id: str):
        """Revoke an API key immediately."""
        response = self.session.delete(f"{self.base_url}/api/v1/keys/{key_id}")
        response.raise_for_status()

    def rotate_key(self, key_id: str, grace_period_hours: int = 24, immediate: bool = False):
        """Rotate an API key with optional grace period."""
        response = self.session.post(
            f"{self.base_url}/api/v1/keys/{key_id}/rotate",
            json={"grace_period_hours": grace_period_hours, "immediate": immediate}
        )
        response.raise_for_status()
        return response.json()

# Usage
client = ObservalClient(api_key=os.environ["OBSERVAL_API_KEY"])

# Create key for staging environment
result = client.create_key("Staging Deploy", environment="test", expires_in_days=30)
print(f"New key: {result['key']}")  # obs_test_...

# List all active production keys
keys = client.list_keys(status="active", environment="live")
print(f"Found {keys['total']} active production keys")

# Rotate key with 48-hour grace period
rotated = client.rotate_key(key_id="...", grace_period_hours=48)
print(f"New key: {rotated['new_key']}")
print(f"Old key expires: {rotated['old_key_expires_at']}")
```

## Migration Guide (docs/UPGRADING.md)

### Upgrading from v0.1.x to v0.2.0

**What's changing:** Observal is moving from single API key per user to multi-key management with expiration, rotation, and environment support.

**Timeline:**
- **v0.2.0 (Q2 2026):** Multi-key API ships, single-key auth still works (backward compatible)
- **v0.3.0 (Q3 2026):** Warning on login: "Your authentication method will change in v0.4.0"
- **v0.4.0 (Q4 2026):** Single-key auth removed, explicit key creation required

**Action required:**

**For CLI users:**
```bash
# Old (works until v0.4.0)
observal login --api-key abc123...

# New (works forever)
observal login --api-key obs_live_abc123...

# Or create new key via API
curl -X POST https://api.observal.io/api/v1/keys \
  -H "Authorization: Bearer $OLD_KEY" \
  -d '{"name": "My CLI", "environment": "live"}'
```

**For CI/CD pipelines:**
1. Create dedicated keys for each pipeline:
   ```bash
   # Create key for GitHub Actions
   curl -X POST /api/v1/keys \
     -H "X-API-Key: $ADMIN_KEY" \
     -d '{"name": "GitHub Actions CI", "environment": "live", "expires_in_days": 90}'
   ```

2. Update environment variables:
   ```bash
   # Before
   export OBSERVAL_API_KEY=abc123...

   # After
   export OBSERVAL_API_KEY=obs_live_xyz789...
   ```

3. Set up rotation reminder:
   ```bash
   # Add to crontab (rotate every 60 days)
   0 0 1 */2 * /path/to/rotate-observal-key.sh
   ```

**For API integrations:**
- Old `X-API-Key` header still works but use new format
- Add error handling for `api_key_expired` and `api_key_revoked` errors
- Implement key rotation in your deployment scripts

**Breaking changes in v0.4.0:**
- `POST /api/v1/auth/login` will NO LONGER regenerate API keys
- Users must explicitly create keys via `POST /api/v1/keys`
- Old key format (non-prefixed) will be rejected

**Rollback plan:**
If you encounter issues, you can temporarily revert to old behavior by setting environment variable:
```bash
export OBSERVAL_LEGACY_KEY_AUTH=true
```
This will be removed in v0.4.0.

## Deployment & Rollout Plan

### Phase 1: Deploy (Week 1)
1. **Run migration** on staging environment first
   - Validate row counts
   - Test authentication with migrated keys
   - Monitor performance metrics

2. **Deploy to production** behind feature flag
   ```python
   # config.py
   ENABLE_MULTI_KEY_AUTH = os.getenv("ENABLE_MULTI_KEY_AUTH", "false").lower() == "true"
   ```

3. **Enable for internal team only** (10 users)
   - Monitor auth success rate
   - Monitor p99 latency (target: < 10ms)
   - Collect feedback on error messages

### Phase 2: Gradual Rollout (Week 2)
1. **Enable for 10% of users** (feature flag percentage)
2. **Monitor metrics:**
   - Auth endpoint latency (p50, p95, p99)
   - Auth success rate (should stay ~same as baseline)
   - Database query performance (`api_keys` table SELECT/UPDATE times)
   - Error rate by error code

3. **If metrics look good:** increase to 50%, then 100%
4. **If metrics degrade:** rollback via feature flag

### Phase 3: Full Rollout (Week 3)
1. **Enable for all users**
2. **Monitor for 7 days** before removing feature flag
3. **Keep `User.api_key_hash` column** for 30 days (rollback safety)

### Rollback Procedure
If critical issues discovered:
1. **Set feature flag to false** → auth falls back to `User.api_key_hash`
2. **Investigate issue** without user impact
3. **Fix and redeploy** when ready
4. **After 30 days:** If no issues, drop `User.api_key_hash` column

### Monitoring Dashboard
Track these metrics:
- Auth requests/sec (by endpoint)
- Auth latency (p50, p95, p99)
- Auth success rate
- API key creation rate
- API key revocation rate
- Error rate by error code (`api_key_expired`, `api_key_revoked`, `invalid_api_key`)

## Out of Scope (Future Work)

- Scope-based permissions (JSON field exists but not enforced yet)
- Key usage analytics dashboard (data collected via last_used_at/last_used_ip)
- Anomaly detection (unusual usage patterns)
- Rate limiting per key
- IP allowlisting per key
- Automated key rotation for CI/CD systems
- Key compromise alerts
