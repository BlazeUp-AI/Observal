"""SAML 2.0 SSO endpoints — placeholder (501 Not Implemented)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/sso/saml", tags=["enterprise-sso"])


@router.post("/login")
async def saml_login():
    """Initiate SAML SSO login."""
    return {"status": 501, "detail": "SAML SSO not yet implemented"}


@router.post("/acs")
async def saml_acs():
    """SAML Assertion Consumer Service callback."""
    return {"status": 501, "detail": "SAML ACS not yet implemented"}


@router.get("/metadata")
async def saml_metadata():
    """SAML Service Provider metadata."""
    return {"status": 501, "detail": "SAML metadata not yet implemented"}
