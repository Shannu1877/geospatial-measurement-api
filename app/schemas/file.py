"""Pydantic schemas for file upload and file information responses."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.common import FileStatus


class FileUploadResponse(BaseModel):
    """Response returned upon successful file upload and processing."""
    id: str = Field(..., description="Unique file UUID", json_schema_extra={"example": "abc123"})
    filename: str = Field(..., description="Original uploaded filename", json_schema_extra={"example": "survey.kml"})
    feature_count: int = Field(..., description="Total number of geographic features extracted", json_schema_extra={"example": 120})
    crs: Optional[str] = Field(default=None, description="Detected source coordinate reference system", json_schema_extra={"example": "EPSG:4326"})
    status: FileStatus = Field(..., description="Current processing lifecycle status", json_schema_extra={"example": "COMPLETED"})


class FileInfoResponse(BaseModel):
    """Detailed file metadata and status response."""
    id: str = Field(..., description="Unique file UUID", json_schema_extra={"example": "abc123"})
    filename: str = Field(..., description="Original uploaded filename", json_schema_extra={"example": "survey.kml"})
    feature_count: int = Field(..., description="Total number of features", json_schema_extra={"example": 120})
    crs: Optional[str] = Field(default=None, description="Coordinate reference system", json_schema_extra={"example": "EPSG:4326"})
    status: FileStatus = Field(..., description="File status (PROCESSING, COMPLETED, FAILED)", json_schema_extra={"example": "COMPLETED"})
    file_size_bytes: int = Field(default=0, description="File size on disk in bytes", json_schema_extra={"example": 45230})
    error_message: Optional[str] = Field(default=None, description="Detailed failure description if status is FAILED")
    created_at: Optional[datetime] = Field(default=None, description="Upload timestamp in UTC")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp in UTC")
