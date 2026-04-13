"""SCIM 2.0 provisioning endpoints — placeholder (501 Not Implemented)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/scim", tags=["enterprise-scim"])


@router.get("/Users")
async def list_users():
    """SCIM list users."""
    return {"status": 501, "detail": "SCIM provisioning not yet implemented"}


@router.post("/Users")
async def create_user():
    """SCIM create user."""
    return {"status": 501, "detail": "SCIM provisioning not yet implemented"}


@router.get("/Users/{user_id}")
async def get_user(user_id: str):
    """SCIM get user."""
    return {"status": 501, "detail": "SCIM provisioning not yet implemented"}


@router.put("/Users/{user_id}")
async def update_user(user_id: str):
    """SCIM update user."""
    return {"status": 501, "detail": "SCIM provisioning not yet implemented"}


@router.delete("/Users/{user_id}")
async def delete_user(user_id: str):
    """SCIM delete user."""
    return {"status": 501, "detail": "SCIM provisioning not yet implemented"}
