"""Coordinate Reference System (CRS) management and transformation service."""

import math
from typing import Any, Optional, Tuple
import pyproj
from shapely.geometry.base import BaseGeometry
import shapely.ops

from app.core.logging import logger
from app.exceptions.custom_exceptions import InvalidCRSException, MissingCRSException


class CRSService:
    """Provides CRS validation, UTM projection selection, and geometry transformations."""

    @staticmethod
    def parse_crs(crs_input: Any) -> Optional[pyproj.CRS]:
        """Parse various CRS inputs into a pyproj.CRS instance.

        Args:
            crs_input: EPSG integer, authority string (e.g. 'EPSG:4326'), WKT, or CRS object.

        Returns:
            pyproj.CRS instance or None if input is empty/None.

        Raises:
            InvalidCRSException: When CRS representation is malformed or invalid.
        """
        if crs_input is None:
            return None

        if isinstance(crs_input, pyproj.CRS):
            return crs_input

        # Handle string or int representations
        try:
            return pyproj.CRS.from_user_input(crs_input)
        except Exception as exc:
            logger.warning("Failed to parse CRS input '%s': %s", crs_input, exc)
            raise InvalidCRSException(f"Invalid or unrecognized CRS specification: {crs_input}") from exc

    @staticmethod
    def format_crs(crs: Optional[pyproj.CRS]) -> Optional[str]:
        """Format pyproj.CRS into a canonical representation string (e.g. 'EPSG:4326')."""
        if crs is None:
            return None

        try:
            # Prefer standard EPSG authority code if available
            epsg = crs.to_epsg()
            if epsg:
                return f"EPSG:{epsg}"
            
            # Fall back to authority name and code (e.g. OGC:CRS84)
            auth = crs.to_authority()
            if auth:
                return f"{auth[0]}:{auth[1]}"

            # Fall back to short name
            return crs.name or "CUSTOM"
        except Exception:
            return "CUSTOM"

    @staticmethod
    def get_utm_epsg_from_lon_lat(lon: float, lat: float) -> int:
        """Calculate the standard WGS84 UTM EPSG code for a given longitude and latitude.

        Args:
            lon: Longitude in degrees (-180 to 180).
            lat: Latitude in degrees (-90 to 90).

        Returns:
            EPSG code as integer (e.g. 32632 for UTM Zone 32N, 32732 for Zone 32S).
        """
        # Clamp latitude to valid bounds
        lat = max(-90.0, min(90.0, lat))

        # Normalize longitude to [-180, 180)
        lon_normalized = ((lon + 180.0) % 360.0) - 180.0
        if lon_normalized == -180.0 and lon > 0:
            lon_normalized = 180.0

        # Calculate UTM zone (1 to 60)
        zone = int((lon_normalized + 180.0) / 6.0) + 1
        zone = max(1, min(60, zone))

        # Polar regions fallback (UPS)
        if lat >= 84.0:
            # Universal Polar Stereographic North
            return 32661
        if lat <= -80.0:
            # Universal Polar Stereographic South
            return 32761

        # UTM North: EPSG 32601 - 32660
        # UTM South: EPSG 32701 - 32760
        if lat >= 0:
            return 32600 + zone
        return 32700 + zone

    @classmethod
    def get_projected_crs_for_geometry(
        cls,
        source_crs: pyproj.CRS,
        geom: BaseGeometry,
    ) -> Tuple[pyproj.CRS, bool]:
        """Determine the most suitable projected CRS for performing accurate metric measurements.

        If the source CRS is already an appropriate projected CRS with linear meter units,
        it is used directly.
        If the source CRS is geographic (degrees), or Web Mercator (EPSG:3857, which has high area distortion),
        a local UTM projection centered on the geometry is dynamically selected.

        Returns:
            Tuple of (target_projected_crs, was_transformed_bool).
        """
        if not source_crs:
            raise MissingCRSException("Cannot determine measurement projection for missing CRS.")

        # EPSG:3857 (Web Mercator) is projected but causes massive area/length distortion away from the equator
        # (scale factor 1/cos(lat)^2). Therefore, we treat it like geographic coordinates and reproject to UTM.
        source_epsg = source_crs.to_epsg()
        is_web_mercator = source_epsg in (3857, 900913)

        if source_crs.is_projected and not is_web_mercator:
            # Already a local or national projected CRS (e.g. UTM, State Plane, BNG)
            return source_crs, False

        # If source is geographic or Web Mercator, compute centroid to pick optimal UTM zone
        if geom.is_empty:
            # Default to WGS84 UTM Zone 31N if geometry is empty
            target_epsg = 32631
            return pyproj.CRS.from_epsg(target_epsg), True

        # Extract representative centroid
        centroid = geom.centroid

        if is_web_mercator:
            # Convert centroid from 3857 to 4326 to find lon/lat
            to_wgs84 = pyproj.Transformer.from_crs(source_crs, pyproj.CRS.from_epsg(4326), always_xy=True)
            lon, lat = to_wgs84.transform(centroid.x, centroid.y)
        else:
            # Source is geographic (EPSG:4326, etc.), centroid.x is lon, centroid.y is lat
            lon, lat = centroid.x, centroid.y

        target_epsg = cls.get_utm_epsg_from_lon_lat(lon, lat)
        target_crs = pyproj.CRS.from_epsg(target_epsg)
        return target_crs, True

    @classmethod
    def transform_geometry(
        cls,
        geom: BaseGeometry,
        source_crs: pyproj.CRS,
        target_crs: pyproj.CRS,
    ) -> BaseGeometry:
        """Transform a Shapely geometry from source_crs to target_crs.

        Guarantees (x, y) = (lon, lat) or (easting, northing) ordering via always_xy=True.
        """
        if source_crs == target_crs:
            return geom

        import numpy as np

        transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

        def _transform_coords(coords: np.ndarray) -> np.ndarray:
            if coords.shape[1] >= 3:
                x, y, z = transformer.transform(coords[:, 0], coords[:, 1], coords[:, 2])
                return np.column_stack((x, y, z))
            x, y = transformer.transform(coords[:, 0], coords[:, 1])
            return np.column_stack((x, y))

        transformed_geom = shapely.transform(geom, _transform_coords)
        return transformed_geom
