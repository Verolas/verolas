"""Per request correlation identifier.

The middleware reads the inbound `X-Request-ID` header if present, otherwise
mints a UUID4. The value is set on the response header so callers can
correlate logs to a single request, and is bound into the structlog context
so every log line inside the request carries it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Bind a request ID for the duration of the request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        token = structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.reset_contextvars(**token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
