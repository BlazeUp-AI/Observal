"""Tests for the 4-tier RBAC system."""

from models.user import User, UserRole


def test_userrole_enum_has_four_tiers():
    """UserRole must have exactly super_admin, admin, reviewer, user."""
    expected = {"super_admin", "admin", "reviewer", "user"}
    actual = {r.value for r in UserRole}
    assert actual == expected, f"Expected {expected}, got {actual}"


def test_userrole_enum_values():
    """Each role's .value matches its name."""
    assert UserRole.super_admin.value == "super_admin"
    assert UserRole.admin.value == "admin"
    assert UserRole.reviewer.value == "reviewer"
    assert UserRole.user.value == "user"


def test_developer_role_does_not_exist():
    """The old 'developer' role must not exist."""
    assert not hasattr(UserRole, "developer"), "developer role should be removed"


def test_user_model_has_is_demo_field():
    """User model must have is_demo boolean field."""
    user = User(
        email="test@example.com",
        name="Test",
        api_key_hash="a" * 64,
    )
    assert user.is_demo is False, "is_demo should default to False"
