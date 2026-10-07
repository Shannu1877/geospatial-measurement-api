"""Pydantic schemas for feature measurements and calculations."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.common import MeasurementStatus


class MeasurementItem(BaseModel):
    """Calculated metric (area or length) for a geospatial feature."""
    type: str = Field(..., description="Measurement type: 'area' or 'length'", json_schema_extra={"example": "area"})
    value: float = Field(..., description="Calculated metric value in standard units", json_schema_extra={"example": 1250.42})
    unit: str = Field(..., description="Unit of measurement ('m²' or 'm')", json_schema_extra={"example": "m²"})


class FeatureMeasurementResponse(BaseModel):
    """Measurement and metadata for a single geospatial feature."""
    feature_id: int = Field(..., description="Zero-based feature index in the dataset", json_schema_extra={"example": 0})
    geometry_type: str = Field(..., description="OGC geometry type", json_schema_extra={"example": "Polygon"})
    crs: Optional[str] = Field(default=None, description="Original CRS identifier", json_schema_extra={"example": "EPSG:4326"})
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature attributes dictionary", json_schema_extra={"example": {"name": "Building A"}})
    measurement: Optional[MeasurementItem] = Field(
        default=None,
        description="Calculated measurement or null for Point/unsupported geometries",
    )
    measurement_status: MeasurementStatus = Field(
        default=MeasurementStatus.COMPLETED,
        description="Processing status for this feature",
        json_schema_extra={"example": "COMPLETED"},
    )


class FileMeasurementsResponse(BaseModel):
    """Measurements response container for all features in a file."""
    file_id: str = Field(..., description="Unique file identifier", json_schema_extra={"example": "abc123"})
    features: List[FeatureMeasurementResponse] = Field(..., description="List of measured features")
