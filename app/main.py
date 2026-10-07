"""FastAPI application factory and main entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import logger
from app.db.database import init_db
from app.exceptions.handlers import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for database initialization and cleanup."""
    logger.info("Initializing Geospatial Measurement API database tables...")
    init_db()
    logger.info("%s v%s started successfully.", settings.APP_NAME, settings.APP_VERSION)
    yield
    logger.info("Shutting down %s...", settings.APP_NAME)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
# Geospatial File Measurement API

A production-quality REST API for uploading, validating, and measuring geospatial vector files.

## Features
- **Supported Formats**: KML (`.kml`) and ESRI Shapefile Archives (`.zip`).
- **Geodesic / Metric Measurement**: Transforms geographic coordinates (`EPSG:4326`) into local UTM projections before calculating areas and lengths, preventing spherical degree distortion.
- **Supported Geometries**:
  - `Polygon` and `MultiPolygon` -> Area in square meters ($m^2$).
  - `LineString` and `MultiLineString` -> Length in meters ($m$).
  - `Point` and `MultiPoint` -> Handled without calculation (`null`).
  - Unsupported/Complex Geometries -> Handled safely with status `UNSUPPORTED`.
- **Security & Integrity**:
  - File size streaming limits.
  - MIME header magic byte verification.
  - Safe ZIP extraction with Zip-Slip path traversal protection.
  - UUID-based on-disk file storage.
  - Sanitized error envelopes without exposing internal stack traces.
        """,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Enable CORS for cross-origin client access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register global exception handlers
    register_exception_handlers(app)

    # Include API routers
    app.include_router(api_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
