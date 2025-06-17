from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pulsr.core.config import settings
from pulsr.core.database import create_db_and_tables
from pulsr.core.exceptions import PulsrHTTPException
from pulsr.api.v1.pipelines import router as pipelines_router
from pulsr.api.v1.runs import router as runs_router

# Import all models to ensure they are registered with SQLModel
from pulsr.models import *


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifecycle events."""
    # Startup
    create_db_and_tables()
    yield
    # Shutdown (nothing needed for now)


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Lightweight ML Pipeline Orchestration API",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    docs_url=f"{settings.api_v1_prefix}/docs",
    redoc_url=f"{settings.api_v1_prefix}/redoc",
    lifespan=lifespan,
)


@app.exception_handler(PulsrHTTPException)
async def pulsr_exception_handler(request: Request, exc: PulsrHTTPException):
    """Handle custom Pulsr HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs_url": f"{settings.api_v1_prefix}/docs",
        "openapi_url": f"{settings.api_v1_prefix}/openapi.json",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Include API routers
app.include_router(pipelines_router, prefix=settings.api_v1_prefix)
app.include_router(runs_router, prefix=settings.api_v1_prefix)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "pulsr.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
