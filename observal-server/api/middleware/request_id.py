"""Request ID middleware.

Assigns a unique UUID to every request and returns it via the ``X-Request-ID``
response header.  If the client supplies a valid UUID in the ``X-Request-ID``
request header it is reused; otherwise a new one is generated.  Invalid values
are silently replaced to prevent header injection.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.requests import Request


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach an ``X-Request-ID`` header to every response."""

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id")
        request_id: str

        if incoming:
            try:
                # Validate that the supplied value is a well-formed UUID.
                request_id = str(uuid.UUID(incoming))
            except (ValueError, AttributeError):
                # Invalid — generate a fresh one instead.
                request_id = str(uuid.uuid4())
        else:
            request_id = str(uuid.uuid4())

        # Stash on request state so downstream handlers can access it.
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
