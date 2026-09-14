from fastapi import FastAPI

from app.api.ai import router as ai_router
from app.api.analysis import router as analysis_router
from app.api.inflation import router as inflation_router
from app.api.release_processing_read import router as release_processing_read_router
from app.api.releases import router as releases_router
from app.api.series import router as series_router

app = FastAPI(
    title="Economic Intelligence API",
    version="0.1.0",
)

app.include_router(series_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(inflation_router, prefix="/api/v1")
app.include_router(releases_router, prefix="/api/v1")
app.include_router(release_processing_read_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}