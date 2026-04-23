from urllib.parse import urlparse

from fastapi import APIRouter, Request

from config import settings

router = APIRouter(prefix="/api/v1/config", tags=["config"])


def derive_endpoints(request: Request | None = None) -> dict[str, str]:
    """Derive all endpoint URLs from settings, falling back to request context."""
    public_url = settings.PUBLIC_URL.rstrip("/") if settings.PUBLIC_URL else ""
    if not public_url and request:
        public_url = str(request.base_url).rstrip("/")
    if not public_url:
        public_url = "http://localhost:8000"

    parsed = urlparse(public_url)
    hostname = parsed.hostname or "localhost"
    scheme = "http" if hostname in ("localhost", "127.0.0.1") else "https"

    otlp_http = settings.OTLP_HTTP_URL.rstrip("/") if settings.OTLP_HTTP_URL else f"{scheme}://{hostname}:4318"
    otlp_grpc = settings.OTLP_GRPC_URL.rstrip("/") if settings.OTLP_GRPC_URL else f"{scheme}://{hostname}:4317"
    web = settings.FRONTEND_URL.rstrip("/") if settings.FRONTEND_URL else f"{scheme}://{hostname}:3000"

    return {
        "api": public_url,
        "otlp_http": otlp_http,
        "otlp_grpc": otlp_grpc,
        "web": web,
    }


@router.get("/endpoints")
async def get_endpoints(request: Request):
    """Endpoint discovery — returns all service URLs. No auth required."""
    return derive_endpoints(request)


@router.get("/public")
async def get_public_config():
    """Public configuration for frontend. No auth required."""
    return {
        "deployment_mode": settings.DEPLOYMENT_MODE,
        "sso_enabled": bool(settings.OAUTH_CLIENT_ID),
        "sso_only": settings.SSO_ONLY,
        "saml_enabled": False,  # placeholder for future ee/ SAML
        "eval_configured": bool(settings.EVAL_MODEL_NAME),
    }
