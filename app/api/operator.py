"""Authorization for operator-only endpoints (Increment #34).

MacroChipz has no user accounts and needs none: there is exactly one
privileged actor (the operator) and a handful of endpoints that only
they should reach -- the three sync routes, each of which drives
outbound provider traffic and writes canonical economic data.

A shared secret in a header is the smallest control that actually
solves that problem. The rejected alternatives are recorded in
ADR-033; the short version is that building accounts, sessions, OAuth
or JWT to protect three operator endpoints would add far more attack
surface and operational burden than it removes.

**Fail closed in production, open in development.** With no token
configured, a production deployment refuses these endpoints outright
rather than leaving them public -- the failure mode of a forgotten
environment variable is then "my sync returns 503", which an operator
notices immediately, rather than "anyone on the internet can drive my
FRED quota", which nobody notices at all.
"""

import secrets

from fastapi import Header, HTTPException

from app.core.config import settings

#: Deliberately not `Authorization`. That header carries connotations
#: (bearer tokens, OAuth, refresh semantics) this is not, and reverse
#: proxies sometimes strip or rewrite it.
OPERATOR_TOKEN_HEADER = "X-Operator-Token"


def require_operator(x_operator_token: str | None = Header(default=None)) -> None:
    """FastAPI dependency guarding every operator-only route.

    Comparison uses `secrets.compare_digest`, so a wrong token takes the
    same time to reject regardless of how many leading characters are
    right. That matters little for a token this long, but the correct
    primitive costs nothing.

    The 401 body never says whether a token was absent, malformed or
    merely wrong -- each of those is a small piece of information a
    prober would like to have.
    """
    configured = settings.operator_token

    if not configured:
        if settings.is_production:
            # Closed, not open. See the module docstring.
            raise HTTPException(
                status_code=503,
                detail="This operation is not available on this server.",
            )
        # Development convenience only: localhost, no secret set.
        return

    if not x_operator_token or not secrets.compare_digest(x_operator_token, configured):
        raise HTTPException(status_code=401, detail="Operator authorization required.")
