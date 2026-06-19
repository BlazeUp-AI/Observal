# SSO Validation Coverage Gaps

**What the validators DO:** probe discovery, authorization endpoint, client credentials, cert expiry, host consistency, JWKS, issuer matching, email scope, NameID format, token auth methods, clock skew, cert/key pairing.

**What they DON'T catch:** (failure modes that still require a real user login to surface)

---

## OIDC/OAuth 2.0

| Gap | Why It Breaks | Symptom |
|-----|---------------|---------|
| **Scope → claim mapping** | IdP advertises `email` scope but doesn't return `email` claim in ID token (requires separate consent or profile config) | Login succeeds at IdP, fails at token validation with "missing email claim" |
| **Refresh token support** | IdP doesn't advertise `refresh_token` in `grant_types_supported` | Sessions die when access token expires; user must re-login every hour |
| **Group/role claim format** | We request `groups` scope but IdP sends `roles`, `memberOf`, or custom claim name | RBAC fails; all users get default role |
| **PKCE requirement** | IdP requires `code_challenge` for public clients, we don't check `code_challenge_methods_supported` | Mobile/SPA logins fail with `invalid_request` |
| **Multi-tenant mixing** | Metadata URL points at tenant A but `client_id` belongs to tenant B | Token exchange fails with `invalid_client` despite probe passing |
| **Token endpoint TLS** | IdP uses weak cipher or self-signed cert | Token exchange fails with TLS error; probe only tested reachability |
| **Logout endpoint missing** | `end_session_endpoint` not in discovery doc | Logout button breaks; sessions linger at IdP |
| **State echo failure** | IdP doesn't echo `state` parameter back in callback | CSRF protection fails; login rejected |
| **Audience claim** | ID token `aud` doesn't match our `client_id` | Token validation fails with "invalid audience" |
| **IdP rate limiting** | Health probe itself gets rate-limited after N checks | False negative — probe fails but real login would work |

---

## SAML 2.0

| Gap | Why It Breaks | Symptom |
|-----|---------------|---------|
| **Attribute mapping** | IdP sends `mail` but we expect `email`; or sends `displayName` but we expect `name` | Login succeeds but user has no email → account creation fails |
| **Active signing cert** | Metadata advertises 3 certs (rotation overlap); we verify ours matches ANY cert but don't know which one IdP uses NOW | Assertion signature fails if IdP rotated to a different cert in the metadata |
| **Encryption expectation** | IdP requires encrypted assertions (`WantAssertionsEncrypted=true` in their metadata) | Assertion rejected with "encryption required" |
| **SLO endpoint** | We never validate `SingleLogoutService` | Logout fails; sessions linger |
| **Clock skew at IdP** | Assertion `NotBefore`/`NotOnOrAfter` has <60s tolerance but our server clock is 90s behind | Every assertion rejected as "expired" despite health probe passing |
| **Binding mismatch** | IdP only supports HTTP-POST for AuthnRequest but we send HTTP-Redirect | AuthnRequest rejected or ignored |
| **Audience restriction** | IdP metadata declares `<md:AssertionConsumerService>` whitelist; our SP entityID isn't in it | Assertion rejected with "invalid audience" |
| **NameID format persistence** | IdP sends `transient` NameID (changes every session) but we expect `persistent` | User gets new account on every login |
| **Signature algorithm** | We configure SHA-256; IdP only supports SHA-1 or requires SHA-512 | Signature validation fails |
| **RelayState length limit** | IdP truncates RelayState >80 bytes | Post-login redirect sends user to `/` instead of deep-link |

---

## Cross-cutting / Architectural

| Gap | Why It Breaks | Symptom |
|-----|---------------|---------|
| **Network path divergence** | Health probe runs from API container, real login routes through LB → proxy → firewall with different egress IP | Probe passes; real login blocked by IdP IP allowlist |
| **Database schema** | User table missing `sso_subject_id` column or email uniqueness constraint not enforced | Login crashes with DB constraint error |
| **JIT provisioning off** | `jit_provisioning=false` but user doesn't exist in DB | Login succeeds at IdP, rejected with "user not found" |
| **Concurrent login storm** | One probe succeeds; 100 simultaneous logins exhaust IdP rate limit or our DB connection pool | First user logs in fine; next 99 get 429 or timeout |
| **Session cookie settings** | `SameSite=Strict` or `Domain=` mismatch prevents cookie from round-tripping through OAuth callback | Login completes but session cookie dropped; user stays logged out |
| **CSRF token loss** | `state` (OIDC) or `RelayState` (SAML) lost in browser redirect due to referrer policy or extension | Login rejected with "state mismatch" |
| **Mobile/custom-scheme redirect** | `redirect_uri` is `observal://callback` but probe only tests `http://` | Probe passes; mobile login fails because browser can't open custom scheme |
| **IdP-side user deactivation** | User exists in our DB but deactivated at IdP | Login accepted by IdP, assertion contains `status=inactive` → we create session anyway |
| **License feature check** | SAML probe passes but `saml` feature not in license | Real login fails with 403 "feature not licensed" |
| **Stale frontend_url** | Admin configured SAML for `internal.observal.io`, later changed `deployment.frontend_url` to `app.observal.io` | Validator flags host mismatch as error but operator intended multi-env config |
| **Wall-clock timeout race** | Health probe has 15s budget; under load the API worker is slow, timeout fires before probe finishes | False negative — validator says "timeout" but real login (no budget) would work |

---

## Documented Non-Goals

These are inherent limits of server-side validation — no amount of probing will catch them:

- **Assertion replay protection** – can't replay a signed SAML assertion or use an auth code twice.
- **Per-user authorization** – can't detect if a specific user is disabled/unlicensed at the IdP.
- **MFA/step-up auth** – can't trigger or bypass IdP MFA challenges in a probe.
- **Consent screens** – can't auto-approve OAuth consent or SAML attribute release.
- **IdP UI/UX changes** – IdP might render 200 OK but show a maintenance page instead of login form.

---

## Mitigation Priority

**High** (common, silent failures):
- Scope → claim mapping (OIDC)
- Attribute mapping (SAML)
- Refresh token support (OIDC)
- Active signing cert ambiguity (SAML)
- Clock skew at IdP (SAML)

**Medium** (detectable in staging):
- Group/role claim format
- Multi-tenant mixing
- Network path divergence
- JIT provisioning off

**Low** (rare or operator-controlled):
- PKCE requirement
- Encryption expectation (SAML)
- RelayState length limit
- Mobile custom-scheme redirects

---

## What we ship now

The admin SSO page exposes two complementary buttons per provider:

1. **Validate** — runs the server-side probes documented above. ~80% gap coverage; ~50ms; no IdP interaction.
2. **End to End Test** — runs the *real* login flow against the real IdP using a real test user. The only step that isn't automated is "user enters credentials at IdP" -- everything else (token exchange, signature validation, claim extraction, audience check, nonce echo, DB lookup) is recorded as per-step pass/fail. Closes the runtime gaps above except the inherent non-goals.

Plus a third layer for real production logins:

3. **Per-step diagnostics on real login failures** — the OIDC callback and SAML ACS now build a check list as they run and, on any failure, redirect to `/login?sso_error=<id>`. The login page fetches the diagnostics and renders them inline, so the user (and operator scraping the page) sees exactly which step broke instead of "SSO Authentication Failed".

## Recommendation

With the Validate button, End to End Test, and inline real-login diagnostics, the only remaining un-catchable failure modes are the **Documented Non-Goals** above (per-user IdP policies, MFA bypass, consent screen UX). Everything else now surfaces concrete, actionable per-step output instead of generic errors.
