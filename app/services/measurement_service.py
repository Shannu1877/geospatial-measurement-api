"""Geometry measurement calculation service for area, length, and unsupported types."""

from typing import Any, Dict, Optional, Tuple
import pyproj
from shapely.geometry.base import BaseGeometry

from app.core.config import settings
from app.core.logging import logger
from app.schemas.common import MeasurementStatus
from app.schemas.measurement import MeasurementItem
from app.services.crs_service import CRSService


class MeasurementService:
    """Computes metric measurements for various Shapely geometry types."""

    # Geometry type classification sets
    AREA_TYPES = {"Polygon", "MultiPolygon"}
    LENGTH_TYPES = {"LineString", "MultiLineString"}
    POINT_TYPES = {"Point", "MultiPoint"}

    @classmethod
    def calculate_measurement(
        cls,
        geom: Optional[BaseGeometry],
        source_crs: Optional[pyproj.CRS],
        precision: Optional[int] = None,
    ) -> Tuple[Optional[MeasurementItem], MeasurementStatus]:
        """Calculate metric measurement (area/length) for a geometry.

        Args:
            geom: Shapely geometry object.
            source_crs: pyproj.CRS instance of the source coordinate system.
            precision: Decimal precision for rounding (defaults to settings.MEASUREMENT_PRECISION).

        Returns:
            Tuple of (MeasurementItem or None, MeasurementStatus).
        """
        prec = precision if precision is not None else settings.MEASUREMENT_PRECISION

        if geom is None or geom.is_empty:
            logger.debug("Geometry is empty or None")
            return None, MeasurementStatus.UNSUPPORTED

        # Point types require no measurement by design
        if geom.geom_type in cls.POINT_TYPES:
            return None, MeasurementStatus.COMPLETED

        # Repair self-intersecting or topologically invalid geometries
        if not geom.is_valid:
            try:
                import shapely
                repaired = shapely.make_valid(geom)
                if not repaired.is_empty:
                    geom = repaired
            except Exception as e:
                logger.warning("Could not repair invalid geometry: %s", e)

        geom_type = geom.geom_type

        # Check for unsupported geometries (e.g. GeometryCollection)
        if geom_type not in cls.AREA_TYPES and geom_type not in cls.LENGTH_TYPES:
            logger.info("Unsupported geometry type encountered: %s", geom_type)
            return None, MeasurementStatus.UNSUPPORTED

        # If CRS is missing, metric measurements cannot be calculated accurately
        if source_crs is None:
            logger.warning("Cannot calculate measurement for feature: missing CRS")
            return None, MeasurementStatus.MISSING_CRS

        try:
            # 1. Select optimal projected CRS (e.g. local UTM zone for geographic coords)
            target_crs, transformed = CRSService.get_projected_crs_for_geometry(source_crs, geom)

            # 2. Transform geometry to projected CRS
            projected_geom = CRSService.transform_geometry(geom, source_crs, target_crs)

            # 3. Calculate metric measurements in projected space
            if geom_type in cls.AREA_TYPES:
                raw_area = float(projected_geom.area)
                rounded_area = round(raw_area, prec)
                return (
                    MeasurementItem(type="area", value=rounded_area, unit="m²"),
                    MeasurementStatus.COMPLETED,
                )

            elif geom_type in cls.LENGTH_TYPES:
                raw_length = float(projected_geom.length)
                rounded_length = round(raw_length, prec)
                return (
                    MeasurementItem(type="length", value=rounded_length, unit="m"),
                    MeasurementStatus.COMPLETED,
                )

        except Exception as exc:
            logger.error(
                "Error calculating measurement for geometry %s: %s",
                geom_type,
                exc,
                exc_info=True,
            )
            return None, MeasurementStatus.ERROR

        return None, MeasurementStatus.UNSUPPORTED
