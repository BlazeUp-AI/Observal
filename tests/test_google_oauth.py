# SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.work@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the Google OAuth provider.

Covers route gating when not configured, email_verified enforcement, domain
allowlist enforcement, user provisioning with provider/subject metadata, and
the domain-allowlist parser.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.responses import RedirectResponse
from httpx import ASGITransport, AsyncClient

from api.ratelimit import limiter
from api.routes import auth as auth_module
from main import app
from services.crypto import init_key_manager


@pytest.fixture(autouse=True, scope="module")
def _init_key_manager(tmp_path_factory):
    key_dir = tmp_path_factory.mktemp("keys")
    init_key_manager(key_dir=str(key_dir), key_password=None)


def _mock_google_client(userinfo: dict | None = None):
    client = MagicMock()
    client.authorize_redirect = AsyncMock()
    client.authorize_access_token = AsyncMock(return_value={"userinfo": userinfo} if userinfo is not None else {})
    return client


@pytest.fixture
async def google_client(monkeypatch):
    """Yields (httpx client, set_google) — set_google swaps oauth.google for the test."""
    limiter.enabled = False

    def set_google(client):
        monkeypatch.setattr(auth_module.oauth, "google", client, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as http:
        yield http, set_google

    app.dependency_overrides.clear()


class TestGoogleOAuthNotConfigured:
    """Routes must 500 cleanly when Google OAuth env vars are unset."""

    @pytest.mark.asyncio
    async def test_login_returns_500_when_not_configured(self, google_client):
        http, set_google = google_client
        set_google(None)
        resp = await http.get("/api/v1/auth/oauth/google/login")
        assert resp.status_code == 500
        assert "not configured" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_callback_returns_500_when_not_configured(self, google_client):
        http, set_google = google_client
        set_google(None)
        resp = await http.get("/api/v1/auth/oauth/google/callback")
        assert resp.status_code == 500
        assert "not configured" in resp.json()["detail"].lower()


class TestGoogleCallback:
    """The /oauth/google/callback handler validates the ID-token claims."""

    @pytest.mark.asyncio
    async def test_rejects_missing_userinfo(self, google_client):
        http, set_google = google_client
        set_google(_mock_google_client())
        resp = await http.get("/api/v1/auth/oauth/google/callback")
        assert resp.status_code == 400
        assert "missing userinfo" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_rejects_missing_email_claim(self, google_client):
        http, set_google = google_client
        set_google(_mock_google_client({"sub": "g-123", "name": "Bob"}))
        resp = await http.get("/api/v1/auth/oauth/google/callback")
        assert resp.status_code == 400
        assert "email" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_rejects_unverified_email(self, google_client):
        http, set_google = google_client
        set_google(
            _mock_google_client(
                {
                    "sub": "g-123",
                    "email": "bob@acme.com",
                    "email_verified": False,
                    "name": "Bob",
                }
            )
        )
        resp = await http.get("/api/v1/auth/oauth/google/callback")
        assert resp.status_code == 400
        assert "not verified" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_rejects_disallowed_domain(self, google_client, monkeypatch):
        http, set_google = google_client
        monkeypatch.setattr(auth_module, "_GOOGLE_ALLOWED_DOMAINS", frozenset({"acme.com", "acme.io"}))
        set_google(
            _mock_google_client(
                {
                    "sub": "g-123",
                    "email": "bob@gmail.com",
                    "email_verified": True,
                    "name": "Bob",
                }
            )
        )
        resp = await http.get("/api/v1/auth/oauth/google/callback")
        assert resp.status_code == 403
        assert "domain" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_allowlisted_domain_reaches_provisioning(self, google_client, monkeypatch):
        """Happy path: claim validation passes, provisioner is called with provider='google'."""
        http, set_google = google_client
        monkeypatch.setattr(auth_module, "_GOOGLE_ALLOWED_DOMAINS", frozenset({"acme.com"}))
        set_google(
            _mock_google_client(
                {
                    "sub": "g-123",
                    "email": "Alice@Acme.com",
                    "email_verified": True,
                    "name": "Alice",
                }
            )
        )

        fake_user = MagicMock()
        fake_user.id = "u-1"
        fake_user.email = "alice@acme.com"
        fake_user.role = MagicMock(value="user")

        provision_mock = AsyncMock(return_value=fake_user)
        complete_mock = AsyncMock(return_value=RedirectResponse(url="http://test/login?code=xxx", status_code=302))
        monkeypatch.setattr(auth_module, "_provision_sso_user", provision_mock)
        monkeypatch.setattr(auth_module, "_complete_sso_login", complete_mock)

        resp = await http.get("/api/v1/auth/oauth/google/callback", follow_redirects=False)

        assert resp.status_code in (302, 307)
        provision_mock.assert_awaited_once()
        kwargs = provision_mock.await_args.kwargs
        assert kwargs["provider"] == "google"
        assert kwargs["email"] == "alice@acme.com"
        assert kwargs["subject_id"] == "g-123"


class TestAllowedDomainsParser:
    """_parse_allowed_domains normalizes the env-supplied list."""

    def test_empty_input_returns_empty_set(self):
        assert auth_module._parse_allowed_domains(None) == set()
        assert auth_module._parse_allowed_domains("") == set()
        assert auth_module._parse_allowed_domains("   ,  ") == set()

    def test_comma_separated_input_is_lowercased_and_stripped(self):
        assert auth_module._parse_allowed_domains("Acme.com, ACME.io ,  ") == {"acme.com", "acme.io"}
