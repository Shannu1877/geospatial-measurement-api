"""Main API router combining all endpoint modules."""

from fastapi import APIRouter
from app.api.routes import files, health

api_router = APIRouter()

# Include health endpoint at root /health
api_router.include_router(health.router)

# Include files router under /api/files
api_router.include_router(files.router, prefix="/api")
