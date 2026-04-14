"""P0 tests for API key management: create, list, revoke, rotate, and authentication."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Request

from models.api_key import ApiKey, ApiKeyEnvironment
from models.user import User, UserRole


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _make_user(
    user_id: uuid.UUID | None = None,
    role: UserRole = UserRole.user,
) -> User:
    """Create a test user."""
    uid = user_id or uuid.uuid4()
    user = User(
        id=uid,
        email=f"test-{uid}@example.com",
        name="Test User",
        role=role,
        api_key_hash=hashlib.sha256(b"legacy-key").hexdigest(),
    )
    return user


def _make_api_key(
    user_id: uuid.UUID,
    name: str = "test-key",
    environment: ApiKeyEnvironment = ApiKeyEnvironment.live,
    expired: bool = False,
    revoked: bool = False,
) -> tuple[ApiKey, str]:
    """Create a test API key. Returns (ApiKey, raw_key)."""
    raw_key = f"obs_{environment.value}_test123456"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    api_key = ApiKey(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        key_hash=key_hash,
        prefix=raw_key[:10],
        environment=environment,
        created_at=datetime.now(UTC),
    )

    if expired:
        api_key.expires_at = datetime.now(UTC) - timedelta(hours=1)
    if revoked:
        api_key.revoked_at = datetime.now(UTC)

    return api_key, raw_key


# ---------------------------------------------------------------------------
# Authentication Tests (P0)
# ---------------------------------------------------------------------------


class TestApiKeyAuthentication:
    """Test authentication using the new ApiKey table."""

    @pytest.mark.asyncio
    async def test_authenticate_with_active_api_key(self):
        """Active API key should authenticate successfully."""
        from api.deps import _authenticate_via_api_key

        user = _make_user()
        api_key, raw_key = _make_api_key(user.id)
        api_key.user = user

        # Mock database to return the API key
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = api_key
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        result = await _authenticate_via_api_key(raw_key, mock_db, mock_request)
        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_authenticate_with_expired_api_key(self):
        """Expired API key should not authenticate."""
        from api.deps import _authenticate_via_api_key

        user = _make_user()
        api_key, raw_key = _make_api_key(user.id, expired=True)
        api_key.user = user

        # Mock database to return the expired API key
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = api_key
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        result = await _authenticate_via_api_key(raw_key, mock_db, mock_request)
        assert result is None  # Expired key returns None

    @pytest.mark.asyncio
    async def test_authenticate_with_revoked_api_key(self):
        """Revoked API key should not authenticate (filtered by query)."""
        from api.deps import _authenticate_via_api_key

        user = _make_user()
        _, raw_key = _make_api_key(user.id, revoked=True)

        # Mock database to return None (revoked keys filtered by WHERE clause)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        # Should fall back to legacy key check which also returns None
        result = await _authenticate_via_api_key(raw_key, mock_db, mock_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_updates_last_used_at(self):
        """Authentication should update last_used_at (debounced)."""
        from api.deps import _authenticate_via_api_key

        user = _make_user()
        api_key, raw_key = _make_api_key(user.id)
        api_key.user = user
        api_key.last_used_at = None  # First use

        # Mock database
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = api_key
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {}

        await _authenticate_via_api_key(raw_key, mock_db, mock_request)

        # Should have updated last_used_at and last_used_ip
        assert api_key.last_used_at is not None
        assert api_key.last_used_ip == "192.168.1.100"
        mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Authorization Tests (P0)
# ---------------------------------------------------------------------------


class TestApiKeyAuthorization:
    """Test that users can only access their own API keys."""

    @pytest.mark.asyncio
    async def test_list_keys_only_returns_own_keys(self):
        """List endpoint should only return keys belonging to current user."""
        from api.routes.keys import list_keys

        user = _make_user()
        other_user = _make_user()

        # User has 2 keys
        key1, _ = _make_api_key(user.id, name="key1")
        key2, _ = _make_api_key(user.id, name="key2")

        # Other user has 1 key (should not be returned)
        other_key, _ = _make_api_key(other_user.id, name="other-key")

        # Mock database to return only user's keys
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [key1, key2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.scalar.return_value = 2  # Total count

        response = await list_keys(
            status=None,
            environment=None,
            sort="created_at",
            limit=50,
            offset=0,
            current_user=user,
            db=mock_db,
        )

        assert response.total == 2
        assert len(response.keys) == 2
        # Verify the query includes user_id filter (would be checked by mock call args)

    @pytest.mark.asyncio
    async def test_revoke_key_only_revokes_own_keys(self):
        """Revoke endpoint should only revoke keys belonging to current user."""
        from api.routes.keys import revoke_key

        user = _make_user()
        other_user = _make_user()

        # Try to revoke another user's key
        other_key, _ = _make_api_key(other_user.id, name="other-key")

        # Mock database to return None (key not found for current user)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await revoke_key(
                key_id=str(other_key.id),
                current_user=user,
                db=mock_db,
            )

        assert exc_info.value.status_code == 404
        # Verify error includes structured response
        assert "key_not_found" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# API Key Lifecycle Tests (P0)
# ---------------------------------------------------------------------------


class TestApiKeyLifecycle:
    """Test create, rotate, and revoke operations."""

    @pytest.mark.asyncio
    async def test_create_key_with_expiration(self):
        """Create key with expiration should set expires_at correctly."""
        from api.routes.keys import create_key
        from schemas.keys import KeyCreateRequest

        user = _make_user()
        request = KeyCreateRequest(
            name="production-key",
            environment=ApiKeyEnvironment.live,
            expires_in_days=90,
        )

        # Mock database with custom refresh that sets id and created_at
        def set_defaults_on_add(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = uuid.uuid4()
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime.now(UTC)

        async def set_defaults_on_refresh(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = uuid.uuid4()
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime.now(UTC)

        mock_db = AsyncMock()
        mock_db.add = MagicMock(side_effect=set_defaults_on_add)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=set_defaults_on_refresh)
        mock_db.scalar = AsyncMock(return_value=0)  # No existing keys

        # Mock request for rate limiter
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        response = await create_key(request=mock_request, req=request, current_user=user, db=mock_db)

        assert response.name == "production-key"
        assert response.environment == ApiKeyEnvironment.live
        assert response.expires_at is not None
        assert response.key.startswith("obs_live_")
        # Verify expiration is approximately 90 days from now
        assert response.expires_at > datetime.now(UTC) + timedelta(days=89)
        assert response.expires_at < datetime.now(UTC) + timedelta(days=91)

    @pytest.mark.asyncio
    async def test_create_key_duplicate_name_fails(self):
        """Creating a key with duplicate name should fail with structured error."""
        from api.routes.keys import create_key
        from schemas.keys import KeyCreateRequest
        from sqlalchemy.exc import IntegrityError

        user = _make_user()
        request = KeyCreateRequest(
            name="duplicate-key",
            environment=ApiKeyEnvironment.live,
        )

        # Mock database to raise IntegrityError on commit
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(side_effect=IntegrityError("", "", "uq_api_keys_user_name"))
        mock_db.rollback = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=0)  # No existing keys

        # Mock request for rate limiter
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        with pytest.raises(HTTPException) as exc_info:
            await create_key(request=mock_request, req=request, current_user=user, db=mock_db)

        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        assert detail["error"] == "duplicate_key_name"
        assert "duplicate-key" in detail["message"]
        assert "docs_url" in detail

    @pytest.mark.asyncio
    async def test_rotate_key_with_grace_period(self):
        """Rotate key should create new key and set grace period on old key."""
        from api.routes.keys import rotate_key
        from schemas.keys import KeyRotateRequest

        user = _make_user()
        old_key, _ = _make_api_key(user.id, name="old-key")

        request = KeyRotateRequest(
            grace_period_hours=48,
            immediate=False,
        )

        # Mock database with custom refresh that sets id
        def set_id_on_add(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = uuid.uuid4()

        async def set_id_on_refresh(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = uuid.uuid4()

        # Mock database to return old key
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = old_key
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.add = MagicMock(side_effect=set_id_on_add)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=set_id_on_refresh)

        response = await rotate_key(
            key_id=str(old_key.id),
            req=request,
            current_user=user,
            db=mock_db,
        )

        assert response.new_key.startswith("obs_")
        assert response.old_key_id == old_key.id
        assert response.grace_period_hours == 48
        # Old key should have expires_at set to ~48 hours from now
        assert old_key.expires_at is not None
        assert old_key.expires_at > datetime.now(UTC) + timedelta(hours=47)
        assert old_key.expires_at < datetime.now(UTC) + timedelta(hours=49)

    @pytest.mark.asyncio
    async def test_rotate_revoked_key_fails(self):
        """Cannot rotate a revoked key."""
        from api.routes.keys import rotate_key
        from schemas.keys import KeyRotateRequest

        user = _make_user()
        revoked_key, _ = _make_api_key(user.id, name="revoked-key", revoked=True)

        request = KeyRotateRequest(immediate=False)

        # Mock database to return revoked key
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = revoked_key
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await rotate_key(
                key_id=str(revoked_key.id),
                req=request,
                current_user=user,
                db=mock_db,
            )

        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        assert detail["error"] == "cannot_rotate_revoked"


# ---------------------------------------------------------------------------
# Key Prefix Tests (P0)
# ---------------------------------------------------------------------------


class TestKeyPrefixes:
    """Test that key prefixes are generated correctly for each environment."""

    def test_live_key_has_live_prefix(self):
        """Live environment keys should have obs_live_ prefix."""
        from api.routes.keys import _generate_api_key

        full_key, key_hash, prefix = _generate_api_key(ApiKeyEnvironment.live)

        assert full_key.startswith("obs_live_")
        assert prefix == full_key[:10]
        assert len(key_hash) == 64  # SHA256 hex digest

    def test_test_key_has_test_prefix(self):
        """Test environment keys should have obs_test_ prefix."""
        from api.routes.keys import _generate_api_key

        full_key, key_hash, prefix = _generate_api_key(ApiKeyEnvironment.test)

        assert full_key.startswith("obs_test_")
        assert prefix == full_key[:10]

    def test_dev_key_has_dev_prefix(self):
        """Dev environment keys should have obs_dev_ prefix."""
        from api.routes.keys import _generate_api_key

        full_key, key_hash, prefix = _generate_api_key(ApiKeyEnvironment.dev)

        assert full_key.startswith("obs_dev_")
        assert prefix == full_key[:10]


# ---------------------------------------------------------------------------
# Legacy Fallback & Edge Cases
# ---------------------------------------------------------------------------


class TestLegacyFallback:
    """Test backward compatibility with legacy User.api_key_hash."""

    @pytest.mark.asyncio
    async def test_legacy_key_authentication(self):
        """Legacy keys stored in User.api_key_hash should still authenticate."""
        from api.deps import _authenticate_via_api_key

        user = _make_user()
        legacy_key = b"legacy-key"
        user.api_key_hash = hashlib.sha256(legacy_key).hexdigest()

        # Mock database to return None for ApiKey table (no new keys)
        # Then return user for legacy lookup
        mock_result_none = MagicMock()
        mock_result_none.scalar_one_or_none.return_value = None

        mock_result_user = MagicMock()
        mock_result_user.scalar_one_or_none.return_value = user

        mock_db = AsyncMock()
        # First call returns None (no ApiKey record), second returns user (legacy)
        mock_db.execute.side_effect = [mock_result_none, mock_result_user]

        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        result = await _authenticate_via_api_key(legacy_key.decode(), mock_db, mock_request)
        assert result.id == user.id


class TestListKeysFiltering:
    """Test list_keys endpoint filtering and sorting."""

    @pytest.mark.asyncio
    async def test_list_active_keys_only(self):
        """List endpoint should filter to active keys only."""
        from api.routes.keys import list_keys

        user = _make_user()

        # Create mock keys: 1 active, 1 expired, 1 revoked
        active_key, _ = _make_api_key(user.id, name="active")
        expired_key, _ = _make_api_key(user.id, name="expired", expired=True)
        revoked_key, _ = _make_api_key(user.id, name="revoked", revoked=True)

        # Mock database to return only active key when filtered
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [active_key]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.scalar.return_value = 1

        response = await list_keys(
            status="active",
            environment=None,
            sort="created_at",
            limit=50,
            offset=0,
            current_user=user,
            db=mock_db,
        )

        assert response.total == 1
        assert len(response.keys) == 1
        assert response.keys[0].name == "active"

    @pytest.mark.asyncio
    async def test_list_by_environment(self):
        """List endpoint should filter by environment."""
        from api.routes.keys import list_keys

        user = _make_user()

        # Create keys in different environments
        live_key, _ = _make_api_key(user.id, name="live-key", environment=ApiKeyEnvironment.live)
        test_key, _ = _make_api_key(user.id, name="test-key", environment=ApiKeyEnvironment.test)

        # Mock database to return only test environment keys
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [test_key]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.scalar.return_value = 1

        response = await list_keys(
            status=None,
            environment=ApiKeyEnvironment.test,
            sort="created_at",
            limit=50,
            offset=0,
            current_user=user,
            db=mock_db,
        )

        assert response.total == 1
        assert response.keys[0].environment == ApiKeyEnvironment.test


class TestRevokeAndRotateEdgeCases:
    """Test edge cases in revoke and rotate operations."""

    @pytest.mark.asyncio
    async def test_revoke_key_success(self):
        """Successful key revocation should set revoked_at."""
        from api.routes.keys import revoke_key

        user = _make_user()
        api_key, _ = _make_api_key(user.id, name="to-revoke")

        # Mock database to return the key
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = api_key
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        await revoke_key(key_id=str(api_key.id), current_user=user, db=mock_db)

        # Verify revoked_at was set
        assert api_key.revoked_at is not None

    @pytest.mark.asyncio
    async def test_rotate_key_immediate(self):
        """Immediate rotation should revoke old key immediately."""
        from api.routes.keys import rotate_key
        from schemas.keys import KeyRotateRequest

        user = _make_user()
        old_key, _ = _make_api_key(user.id, name="old-key")

        request = KeyRotateRequest(immediate=True)

        def set_id_on_add(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = uuid.uuid4()

        async def set_id_on_refresh(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = old_key
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.add = MagicMock(side_effect=set_id_on_add)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=set_id_on_refresh)

        response = await rotate_key(
            key_id=str(old_key.id),
            req=request,
            current_user=user,
            db=mock_db,
        )

        # Old key should be revoked immediately
        assert old_key.revoked_at is not None
        assert response.old_key_expires_at <= datetime.now(UTC) + timedelta(seconds=1)


class TestAuthenticationDebounce:
    """Test debounce behavior in authentication."""

    @pytest.mark.asyncio
    async def test_last_used_not_updated_within_minute(self):
        """last_used_at should not update if last update was < 1 minute ago."""
        from api.deps import _authenticate_via_api_key

        user = _make_user()
        api_key, raw_key = _make_api_key(user.id)
        api_key.user = user

        # Set last_used_at to 30 seconds ago (within 1 minute)
        api_key.last_used_at = datetime.now(UTC) - timedelta(seconds=30)
        initial_last_used = api_key.last_used_at

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = api_key
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        await _authenticate_via_api_key(raw_key, mock_db, mock_request)

        # last_used_at should NOT have changed
        assert api_key.last_used_at == initial_last_used
        # commit should not have been called
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_ip_from_x_forwarded_for(self):
        """Should extract client IP from x-forwarded-for header."""
        from api.deps import _authenticate_via_api_key

        user = _make_user()
        api_key, raw_key = _make_api_key(user.id)
        api_key.user = user
        api_key.last_used_at = None  # First use

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = api_key
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        # Mock request with x-forwarded-for header (proxy scenario)
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "10.0.0.1"  # Internal proxy IP
        mock_request.headers = {"x-forwarded-for": "203.0.113.42, 198.51.100.17"}

        await _authenticate_via_api_key(raw_key, mock_db, mock_request)

        # Should extract the first IP from x-forwarded-for
        assert api_key.last_used_ip == "203.0.113.42"
