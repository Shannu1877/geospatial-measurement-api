"""Health check endpoint router."""

from fastapi import APIRouter
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Check the operational health status of the Geospatial Measurement API.",
)
async def health_check() -> HealthResponse:
    """Return operational status."""
    return HealthResponse(status="ok")
