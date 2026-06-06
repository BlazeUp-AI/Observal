# SPDX-FileCopyrightText: 2026 Apoorv Garg <apoorvgarg.21@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the Google OAuth provider.

Covers route gating when not configured, email_verified enforcement, domain
allowlist enforcement, user provisioning with provider/subject metadata, and
the domain-allowlist parser.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True, scope="module")
def _init_key_manager(tmp_path_factory):
    from services.crypto import init_key_manager

    key_dir = tmp_path_factory.mktemp("keys")
    init_key_manager(key_dir=str(key_dir), key_password=None)


def _make_async_client():
    from httpx import ASGITransport, AsyncClient

    from api.ratelimit import limiter
    from main import app

    limiter.enabled = False

    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


def _cleanup():
    from main import app

    app.dependency_overrides.clear()


def _mock_google_client(userinfo: dict):
    client = MagicMock()
    client.authorize_redirect = AsyncMock()
    client.authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})
    return client


class TestGoogleOAuthNotConfigured:
    """Routes must 500 cleanly when Google OAuth env vars are unset."""

    @pytest.mark.asyncio
    async def test_login_returns_500_when_not_configured(self):
        from api.routes import auth as auth_module

        with patch.object(auth_module.oauth, "google", None, create=True):
            async with _make_async_client() as client:
                resp = await client.get("/api/v1/auth/oauth/google/login")
            assert resp.status_code == 500
            assert "not configured" in resp.json()["detail"].lower()
        _cleanup()

    @pytest.mark.asyncio
    async def test_callback_returns_500_when_not_configured(self):
        from api.routes import auth as auth_module

        with patch.object(auth_module.oauth, "google", None, create=True):
            async with _make_async_client() as client:
                resp = await client.get("/api/v1/auth/oauth/google/callback")
            assert resp.status_code == 500
            assert "not configured" in resp.json()["detail"].lower()
        _cleanup()


class TestGoogleCallback:
    """The /oauth/google/callback handler validates the ID-token claims."""

    @pytest.mark.asyncio
    async def test_rejects_missing_userinfo(self):
        from api.routes import auth as auth_module

        google = MagicMock()
        google.authorize_access_token = AsyncMock(return_value={})
        with patch.object(auth_module.oauth, "google", google, create=True):
            async with _make_async_client() as client:
                resp = await client.get("/api/v1/auth/oauth/google/callback")
            assert resp.status_code == 400
            assert "missing userinfo" in resp.json()["detail"].lower()
        _cleanup()

    @pytest.mark.asyncio
    async def test_rejects_missing_email_claim(self):
        from api.routes import auth as auth_module

        google = _mock_google_client({"sub": "g-123", "name": "Bob"})
        with patch.object(auth_module.oauth, "google", google, create=True):
            async with _make_async_client() as client:
                resp = await client.get("/api/v1/auth/oauth/google/callback")
            assert resp.status_code == 400
            assert "email" in resp.json()["detail"].lower()
        _cleanup()

    @pytest.mark.asyncio
    async def test_rejects_unverified_email(self):
        from api.routes import auth as auth_module

        google = _mock_google_client(
            {
                "sub": "g-123",
                "email": "bob@acme.com",
                "email_verified": False,
                "name": "Bob",
            }
        )
        with patch.object(auth_module.oauth, "google", google, create=True):
            async with _make_async_client() as client:
                resp = await client.get("/api/v1/auth/oauth/google/callback")
            assert resp.status_code == 400
            assert "not verified" in resp.json()["detail"].lower()
        _cleanup()

    @pytest.mark.asyncio
    async def test_rejects_disallowed_domain(self, monkeypatch):
        from api.routes import auth as auth_module

        monkeypatch.setattr(auth_module.settings, "GOOGLE_OAUTH_ALLOWED_DOMAINS", "acme.com,acme.io")
        google = _mock_google_client(
            {
                "sub": "g-123",
                "email": "bob@gmail.com",
                "email_verified": True,
                "name": "Bob",
            }
        )
        with patch.object(auth_module.oauth, "google", google, create=True):
            async with _make_async_client() as client:
                resp = await client.get("/api/v1/auth/oauth/google/callback")
            assert resp.status_code == 403
            assert "domain" in resp.json()["detail"].lower()
        _cleanup()

    @pytest.mark.asyncio
    async def test_allowlisted_domain_reaches_provisioning(self, monkeypatch):
        """Happy path: claim validation passes, provisioner is called with provider='google'."""
        from fastapi.responses import RedirectResponse

        from api.routes import auth as auth_module

        monkeypatch.setattr(auth_module.settings, "GOOGLE_OAUTH_ALLOWED_DOMAINS", "acme.com")
        google = _mock_google_client(
            {
                "sub": "g-123",
                "email": "Alice@Acme.com",
                "email_verified": True,
                "name": "Alice",
            }
        )
        fake_user = MagicMock()
        fake_user.id = "u-1"
        fake_user.email = "alice@acme.com"
        fake_user.role = MagicMock(value="user")

        provision_mock = AsyncMock(return_value=fake_user)
        complete_mock = AsyncMock(return_value=RedirectResponse(url="http://test/login?code=xxx", status_code=302))

        with (
            patch.object(auth_module.oauth, "google", google, create=True),
            patch.object(auth_module, "_provision_sso_user", provision_mock),
            patch.object(auth_module, "_complete_sso_login", complete_mock),
        ):
            async with _make_async_client() as client:
                resp = await client.get("/api/v1/auth/oauth/google/callback", follow_redirects=False)

        assert resp.status_code in (302, 307)
        provision_mock.assert_awaited_once()
        kwargs = provision_mock.await_args.kwargs
        assert kwargs["provider"] == "google"
        assert kwargs["email"] == "alice@acme.com"
        assert kwargs["subject_id"] == "g-123"
        _cleanup()


class TestAllowedDomainsParser:
    """_parse_allowed_domains normalizes the env-supplied list."""

    def test_empty_input_returns_empty_set(self):
        from api.routes.auth import _parse_allowed_domains

        assert _parse_allowed_domains(None) == set()
        assert _parse_allowed_domains("") == set()
        assert _parse_allowed_domains("   ,  ") == set()

    def test_comma_separated_input_is_lowercased_and_stripped(self):
        from api.routes.auth import _parse_allowed_domains

        assert _parse_allowed_domains("Acme.com, ACME.io ,  ") == {"acme.com", "acme.io"}
