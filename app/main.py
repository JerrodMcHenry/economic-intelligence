from fastapi import FastAPI
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
from app.core.schema_compatibility import SchemaCompatibilityStatus, check_schema_compatibility
from app.core.version import application_version
from app.models.readiness import ReadinessReason, ReadinessResponse

app = FastAPI(
    title="Economic Intelligence API",
    version="0.1.0",
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