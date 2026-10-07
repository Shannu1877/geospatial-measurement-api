"""Common Pydantic models and response wrappers."""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class FileStatus(str, Enum):
    """File processing lifecycle status."""
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MeasurementStatus(str, Enum):
    """Measurement computation status for individual features."""
    COMPLETED = "COMPLETED"
    UNSUPPORTED = "UNSUPPORTED"
    MISSING_CRS = "MISSING_CRS"
    ERROR = "ERROR"


class ErrorDetail(BaseModel):
    """Structured error payload."""
    code: str = Field(..., description="Machine-readable error code", json_schema_extra={"example": "INVALID_FILE"})
    message: str = Field(..., description="Human-readable error description", json_schema_extra={"example": "The uploaded ZIP does not contain a valid Shapefile."})
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optional extra diagnostic details")


class ErrorResponse(BaseModel):
    """Top-level error response envelope."""
    error: ErrorDetail


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="ok", json_schema_extra={"example": "ok"})
