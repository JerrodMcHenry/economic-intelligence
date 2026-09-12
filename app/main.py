from fastapi import FastAPI

from app.api.analysis import router as analysis_router
from app.api.series import router as series_router

app = FastAPI(
    title="Economic Intelligence API",
    version="0.1.0",
)

app.include_router(series_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}