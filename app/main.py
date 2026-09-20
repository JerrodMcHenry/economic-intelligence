import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.ai import router as ai_router
from app.api.analysis import router as analysis_router
from app.api.analyst import router as analyst_router
from app.api.inflation import router as inflation_router
from app.api.labor import router as labor_router
from app.api.monitor_history import router as monitor_history_router
from app.api.rates import monitors_router as rates_monitors_router, rates_router
from app.api.release_processing_read import router as release_processing_read_router
from app.api.releases import router as releases_router
from app.api.series import router as series_router
from app.api.since_last_visit import router as since_last_visit_router
from app.api.middleware import BodySizeLimitMiddleware, RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.config import production_configuration_errors, settings
from app.core.logging import configure_logging
from app.core.schema_compatibility import SchemaCompatibilityStatus, check_schema_compatibility
from app.core.version import application_version
from app.models.readiness import ReadinessReason, ReadinessResponse

configure_logging()
logger = logging.getLogger("app.main")

# A production deployment that is missing something production needs
# should say so once, loudly, at startup -- not discover it at the first
# request that happens to need it. Names only, never values, so these
# lines are safe in any deploy log.
for _problem in production_configuration_errors():
    logger.error("production configuration problem", extra={"problem": _problem})

app = FastAPI(
    title="Economic Intelligence API",
    version="0.1.0",
    # Interactive docs are development-only by default: in production
    # their main effect is to hand a scanner a map of the operator
    # endpoints (see ADR-033).
    docs_url="/docs" if settings.expose_api_docs else None,
    redoc_url="/redoc" if settings.expose_api_docs else None,
    openapi_url="/openapi.json" if settings.expose_api_docs else None,
)

# Middleware order is the reverse of registration, so the LAST registered
# runs first. Body-size limiting must run before anything buffers a body,
# and request context must wrap everything so even a rejected request is
# logged and carries an id.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(RequestContextMiddleware)

# Explicit origin allowlist, never a wildcard, and no credentials: this
# API has no cookies or sessions to protect, and `allow_credentials`
# with a wildcard is the specific combination browsers reject anyway.
# Empty locally is correct -- the Vite dev server proxies `/api`
# same-origin, so no preflight ever occurs in development.
if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Operator-Token", "X-Request-ID"],
        max_age=600,
    )

app.include_router(series_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(inflation_router, prefix="/api/v1")
app.include_router(labor_router, prefix="/api/v1")
app.include_router(rates_monitors_router, prefix="/api/v1")
app.include_router(rates_router, prefix="/api/v1")
app.include_router(monitor_history_router, prefix="/api/v1")
app.include_router(releases_router, prefix="/api/v1")
app.include_router(release_processing_read_router, prefix="/api/v1")
app.include_router(since_last_visit_router, prefix="/api/v1")
# The Increment-8 tool-calling AI path, superseded by the #33 Analyst.
# Left in the repository (removing it is not this increment's job) but
# NOT routed: it accepts an unbounded `message` and can issue up to five
# provider calls per request, which is the largest anonymous cost
# surface in the application. Opt-in locally; never in production.
if settings.enable_legacy_ai_route and not settings.is_production:
    app.include_router(ai_router, prefix="/api/v1")
app.include_router(analyst_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    """Process liveness only -- deliberately never touches the
    database (docs/product/production-reliability-deployment-v1.md
    §15). Answers "is this process alive at all", never "is it safe to
    route traffic here" -- see `/readiness` for that question. Stays
    unconditionally `200 {"status": "ok"}` even while `/readiness`
    reports the instance unready (#26B's own frozen health-vs-readiness
    split, §37 of #26C's own test matrix)."""
    return {"status": "ok"}


# Maps this module's own richer, internal SchemaCompatibilityStatus
# (app/core/schema_compatibility.py) onto #26B's own frozen, coarser,
# public three-value reason vocabulary (§19) -- SCHEMA_BEHIND/
# SCHEMA_AHEAD/SCHEMA_UNINITIALIZED/SCHEMA_AMBIGUOUS all summarize to
# the single public "schema_mismatch" reason; the finer distinction
# remains privately inspectable via the separate expected/actual
# revision strings the response already carries.
_READINESS_REASON: dict[SchemaCompatibilityStatus, ReadinessReason] = {
    SchemaCompatibilityStatus.SCHEMA_BEHIND: "schema_mismatch",
    SchemaCompatibilityStatus.SCHEMA_AHEAD: "schema_mismatch",
    SchemaCompatibilityStatus.SCHEMA_UNINITIALIZED: "schema_mismatch",
    SchemaCompatibilityStatus.SCHEMA_AMBIGUOUS: "schema_mismatch",
    SchemaCompatibilityStatus.DATABASE_UNAVAILABLE: "database_unreachable",
    SchemaCompatibilityStatus.CONFIGURATION_MISSING: "configuration_missing",
}


@app.get("/readiness", response_model=ReadinessResponse)
def readiness() -> JSONResponse:
    """Is it safe to route real traffic to this instance? --
    docs/product/production-reliability-deployment-v1.md §14/§15/§16.

    Evaluates database reachability and schema compatibility
    (`app.core.schema_compatibility.check_schema_compatibility`, the
    one, shared compatibility check `app/operations/process_release.py`
    and `app/operations/run_maintenance.py` also use, §20) -- nothing
    else. Never calls FRED or any external provider, never runs a
    migration, never performs an economic calculation (#26B §14's own
    "readiness must not require an external provider to succeed" rule,
    generalized here to "readiness never does anything beyond checking
    reachability and schema compatibility").

    `200` with `ready: true` only when the schema exactly matches this
    application's own expected Alembic head (#26B §8/§9's V1 exact-
    equality policy). `503` with `ready: false` and a public-safe
    `reason` otherwise -- this route itself never raises, crashes, or
    mutates the database; a schema mismatch is reported, never treated
    as a reason to fail the request itself (#26B §16: remain alive,
    report unready, never crash-loop).
    """
    result = check_schema_compatibility()
    reason = None if result.compatible else _READINESS_REASON[result.status]
    body = ReadinessResponse(
        ready=result.compatible,
        reason=reason,
        expected_schema_revision=result.expected_revision,
        actual_schema_revision=result.actual_revision,
        version=application_version(),
    )
    return JSONResponse(status_code=200 if result.compatible else 503, content=body.model_dump())