"""Restricted-demo access control (Increment #55A, ADR-042).

MacroChipz's first deployment is a restricted demonstration, not a
public launch: Inflation and Jobs are built on FRED-distributed data
whose redistribution terms are unresolved (#46B §D, #54B). So nothing
the deployment holds -- the frontend, generated share pages, the
sitemap, static assets or any API response -- may be served to someone
who has not authenticated.

Why this lives in the application rather than at the platform: Render
offers no authentication for web services or static sites (#55A
research, recorded in ADR-042). An unlisted URL, `robots.txt`, or a
login screen drawn by the frontend would each leave every byte one
`curl` away. This middleware runs in front of every route, so there is
no path to data that skips it -- and the frontend is served by this
same process (`app/web/frontend.py`) precisely so that it sits behind
the same check.

Mechanism: HTTP Basic authentication over the platform's TLS. It is
the smallest control that is real: browser-native (no login page, no
frontend change, no session store), sent with every request including
the frontend's own same-origin `fetch` calls, and verifiable with
`curl -u`. Its known costs are accepted and written down in ADR-042:
no logout short of closing the browser, and one shared credential.

**Fail closed.** In production the gate is always on. With
`ACCESS_PASSWORD` unset or too short, every request except `/health`
receives 503 -- a forgotten variable yields an unavailable site, never
a public one.

Exactly one path is exempt: `/health`, because the platform's health
check cannot authenticate. It returns `{"status": "ok"}` and touches
nothing else (see `app/main.py`).
"""

import base64
import binascii
import logging
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.rate_limit import FixedWindowRateLimiter, client_key
from app.core.config import settings

logger = logging.getLogger("app.api.access_gate")

#: The ONLY unauthenticated path. A test enumerates every route and
#: asserts each one is gated unless it is listed here.
EXEMPT_PATHS = frozenset({"/health"})

REALM = "MacroChipz restricted demo"

#: Failed attempts -- requests that PRESENT wrong credentials -- allowed
#: per client per window before the gate stops checking credentials for
#: that client at all. This bounds casual
#: guessing; `X-Forwarded-For` is forgeable, so it cannot stop a
#: determined attacker -- the password's length (MIN_ACCESS_PASSWORD_LENGTH,
#: generated randomly per the deployment checklist) is what does.
FAILED_ATTEMPTS_PER_WINDOW = 10
FAILED_ATTEMPT_WINDOW_SECONDS = 300

_failed_attempts = FixedWindowRateLimiter(
    limit=FAILED_ATTEMPTS_PER_WINDOW,
    window_seconds=FAILED_ATTEMPT_WINDOW_SECONDS,
)

#: Added to every gated response. Not access control -- a courtesy to
#: well-behaved crawlers that meet the 401, and a second signal that
#: nothing here is meant to be indexed.
ROBOTS_HEADER = ("X-Robots-Tag", "noindex, nofollow")


class AccessGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS or not settings.access_gate_required:
            return await call_next(request)

        if not settings.access_password_usable:
            # Closed, not open. `production_configuration_errors()` has
            # already named the missing variable at startup.
            return _gated(JSONResponse(status_code=503, content={"detail": "This service is not available."}))

        key = client_key(request.client.host if request.client else None, request.headers.get("x-forwarded-for"))
        if _failed_attempts.is_limited(key):
            return _gated(
                JSONResponse(
                    status_code=429,
                    content={"detail": "Too many failed sign-in attempts. Please wait and try again."},
                    headers={"Retry-After": str(_failed_attempts.retry_after_seconds(key))},
                )
            )

        authorization = request.headers.get("authorization")
        if not _credentials_match(authorization):
            # Only a PRESENTED credential is a guess. A request with none
            # is the normal first step of the Basic challenge -- and is
            # what link unfurlers and monitors send -- so counting it
            # would let anonymous traffic from a shared address lock a
            # reviewer out. (#55A: found when the container checks'
            # own anonymous probes locked out the authenticated client.)
            if authorization:
                _failed_attempts.allow(key)
            # The request id and route are already logged by
            # RequestContextMiddleware; the header itself never is.
            logger.info("access denied", extra={"request_id": getattr(request.state, "request_id", None)})
            return _gated(
                JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required."},
                    headers={"WWW-Authenticate": f'Basic realm="{REALM}", charset="UTF-8"'},
                )
            )

        response = await call_next(request)
        response.headers.setdefault(*ROBOTS_HEADER)
        return response


def _gated(response: JSONResponse) -> JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    response.headers[ROBOTS_HEADER[0]] = ROBOTS_HEADER[1]
    return response


def _credentials_match(authorization: str | None) -> bool:
    """Constant-time comparison of both fields. Malformed, absent and
    wrong credentials are indistinguishable to the caller."""
    scheme, _, encoded = (authorization or "").partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return False
    try:
        decoded = base64.b64decode(encoded.strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    username, separator, password = decoded.partition(":")
    if not separator:
        return False

    # Both comparisons always run, so timing does not reveal which
    # field was wrong.
    username_ok = secrets.compare_digest(username.encode(), settings.access_username.encode())
    password_ok = secrets.compare_digest(password.encode(), (settings.access_password or "").encode())
    return username_ok and password_ok


def reset_failed_attempts() -> None:
    """Test-only."""
    _failed_attempts.reset()
