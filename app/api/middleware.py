"""HTTP middleware (Increment #34).

Three small, independent pieces of ASGI middleware, each solving one
audited problem and nothing else:

- `RequestContextMiddleware` — gives every request an id, logs one
  structured line per request, and returns the id in a header so a user
  reporting a problem can quote something that finds the exact request.
- `BodySizeLimitMiddleware` — rejects oversized bodies before they are
  buffered and parsed.
- `SecurityHeadersMiddleware` — the response headers that are genuinely
  the API's to set.

Deliberately plain ASGI/`BaseHTTPMiddleware` rather than a framework:
three small behaviours do not justify a dependency, and each is easier
to reason about written out.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

logger = logging.getLogger("app.api.request")

#: Echoed back on every response.
REQUEST_ID_HEADER = "X-Request-ID"

#: Security headers this API genuinely owns.
#:
#: Note what is absent and why. `Content-Security-Policy` is NOT set
#: here: this service returns JSON, never HTML, so a CSP on these
#: responses protects nothing. The CSP that matters belongs to the
#: static host serving the frontend, and pretending to set it here would
#: be theatre -- it is specified instead in the deployment document.
#: `Strict-Transport-Security` is sent in production only -- see
#: `STRICT_TRANSPORT_SECURITY` below (#55A reversed #34's omission).
SECURITY_HEADERS = {
    # Browsers must not sniff a JSON body into something executable.
    "X-Content-Type-Options": "nosniff",
    # Nothing here should ever be framed.
    "X-Frame-Options": "DENY",
    # Never leak a full API URL (which can carry query parameters) to a
    # third-party origin.
    "Referrer-Policy": "no-referrer",
    # This API needs no browser capability at all.
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id, emit one structured access line, echo the id.

    The log line deliberately carries the route TEMPLATE
    (`/api/v1/series/{series_id}`) rather than the concrete path: paths
    contain user-supplied identifiers, and a template aggregates
    properly while a raw path does not.
    """

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER)
        # An inbound id is echoed so a proxy or client can correlate,
        # but it is length-capped: it ends up in a log line and a
        # response header, and neither should accept unbounded text.
        request_id = (incoming or "")[:64].strip() or uuid.uuid4().hex
        request.state.request_id = request_id

        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.error(
                "request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": _route_template(request),
                    "status_code": 500,
                    "duration_ms": duration_ms,
                },
            )
            raise

        duration_ms = int((time.monotonic() - started) * 1000)
        response.headers[REQUEST_ID_HEADER] = request_id

        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": _route_template(request),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path_format = getattr(route, "path_format", None) or getattr(route, "path", None)
    return path_format or request.url.path


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject a request body larger than the configured maximum.

    Checks `Content-Length` first, which rejects the common case before
    a single byte is buffered. A chunked request has no declared length,
    so the stream is counted as it arrives and abandoned once it exceeds
    the limit -- bounded either way.

    Every legitimate request to this API is a small JSON document; the
    largest contracted field is the Analyst's 500-character question.
    """

    async def dispatch(self, request: Request, call_next):
        limit = settings.max_request_body_bytes

        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > limit:
                    return _too_large(limit)
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Malformed Content-Length header."})

        if request.headers.get("transfer-encoding", "").lower() == "chunked":
            total = 0
            chunks: list[bytes] = []
            async for chunk in request.stream():
                total += len(chunk)
                if total > limit:
                    return _too_large(limit)
                chunks.append(chunk)
            body = b"".join(chunks)

            # Re-serve the already-consumed stream to the application.
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = receive  # noqa: SLF001 -- the documented way to replay a consumed stream

        return await call_next(request)


def _too_large(limit: int) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={"detail": f"Request body exceeds the {limit}-byte limit."},
    )


#: Production only (#55A). #34 omitted HSTS on the assumption that the
#: platform edge issues it; #55A's review of Render's documentation found
#: no such statement, so the application sends it. Safe because Render
#: redirects every HTTP request to HTTPS before it arrives here. No
#: `includeSubDomains`: the default host is a subdomain of onrender.com.
STRICT_TRANSPORT_SECURITY = ("Strict-Transport-Security", "max-age=31536000")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach `SECURITY_HEADERS` to every response, including errors."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        # `Response.headers` is already a MutableHeaders; `setdefault`
        # means a route that deliberately sets its own value wins.
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if settings.is_production:
            response.headers.setdefault(*STRICT_TRANSPORT_SECURITY)
        return response
