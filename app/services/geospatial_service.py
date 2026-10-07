"""Geospatial processing service for reading, parsing, and extracting vector features."""

import math
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry.base import BaseGeometry

from app.core.logging import logger
from app.exceptions.custom_exceptions import (
    CorruptGeospatialFileException,
    InvalidFileException,
    MissingCRSException,
)
from app.schemas.measurement import FeatureMeasurementResponse, MeasurementItem
from app.services.crs_service import CRSService
from app.services.measurement_service import MeasurementService
from app.utils.file_utils import cleanup_directory, safe_extract_zip


def sanitize_property_value(val: Any) -> Any:
    """Ensure property values are JSON-serializable and clean of NaNs."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float, str, bool)):
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def sanitize_properties(props: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize all attributes in a property dictionary."""
    return {k: sanitize_property_value(v) for k, v in props.items() if k != "geometry"}


class GeospatialService:
    """Handles vector dataset ingestion, layer extraction, CRS detection, and feature parsing."""

    @classmethod
    def read_geospatial_dataset(
        cls,
        file_path: Path,
        extension: str,
    ) -> Tuple[gpd.GeoDataFrame, Optional[str]]:
        """Read vector dataset into GeoDataFrame and resolve its CRS string.

        Args:
            file_path: Path to stored .kml or .zip file.
            extension: Normalized extension (.kml or .zip).

        Returns:
            Tuple of (GeoDataFrame, crs_string_or_None).

        Raises:
            CorruptGeospatialFileException: When GIS driver fails to parse file.
            InvalidFileException: When archive structure is invalid.
        """
        temp_dir: Optional[Path] = None

        try:
            if extension == ".kml":
                logger.info("Reading KML dataset from %s", file_path)
                try:
                    # Check available layers in KML
                    layers = pyogrio.list_layers(file_path)
                    if len(layers) == 0:
                        raise CorruptGeospatialFileException("KML file contains no readable vector layers.")

                    # Read all layers and concatenate
                    dfs = []
                    for layer_info in layers:
                        layer_name = str(layer_info[0]) if hasattr(layer_info, "__getitem__") else str(layer_info)
                        try:
                            df = gpd.read_file(file_path, layer=layer_name, engine="pyogrio")
                            if not df.empty:
                                dfs.append(df)
                        except Exception as e:
                            logger.warning("Could not read KML layer '%s': %s", layer_name, e)

                    if dfs:
                        gdf = pd.concat(dfs, ignore_index=True)
                        gdf = gpd.GeoDataFrame(gdf, geometry="geometry")
                    else:
                        # Fallback to default read
                        gdf = gpd.read_file(file_path, engine="pyogrio")

                except (pyogrio.errors.DataSourceError, Exception) as exc:
                    logger.error("Failed to read KML dataset %s: %s", file_path, exc)
                    raise CorruptGeospatialFileException(f"Failed to read KML file: {str(exc)}") from exc

                # Per OGC KML 2.2 Specification (§6.1), KML geometries are defined in WGS84 (EPSG:4326)
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)

            elif extension == ".zip":
                logger.info("Extracting and reading Shapefile ZIP from %s", file_path)
                temp_dir = Path(tempfile.mkdtemp(prefix="shp_extract_"))
                shp_path = safe_extract_zip(file_path, temp_dir)

                try:
                    gdf = gpd.read_file(shp_path, engine="pyogrio")
                except (pyogrio.errors.DataSourceError, Exception) as exc:
                    logger.error("Failed to read Shapefile %s: %s", shp_path, exc)
                    raise CorruptGeospatialFileException(
                        f"Failed to decode Shapefile: {str(exc)}"
                    ) from exc

            else:
                raise InvalidFileException(f"Unsupported file format '{extension}'.")

            crs_obj = CRSService.parse_crs(gdf.crs)
            crs_str = CRSService.format_crs(crs_obj)
            logger.info("Dataset read successfully. Features: %d, CRS: %s", len(gdf), crs_str)
            return gdf, crs_str

        finally:
            if temp_dir:
                cleanup_directory(temp_dir)

    @classmethod
    def process_features(
        cls,
        gdf: gpd.GeoDataFrame,
        crs_str: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Process all features in GeoDataFrame, computing measurements and structuring output.

        Returns list of feature dictionaries ready for database storage and API response.
        """
        source_crs = CRSService.parse_crs(gdf.crs)
        features: List[Dict[str, Any]] = []

        for idx, row in gdf.iterrows():
            geom: Optional[BaseGeometry] = row.geometry if hasattr(row, "geometry") else None
            geom_type = geom.geom_type if (geom is not None and not geom.is_empty) else "Unknown"

            # Extract row properties
            props = row.drop(labels=["geometry"], errors="ignore").to_dict()
            clean_props = sanitize_properties(props)

            # Compute measurement
            measurement, status = MeasurementService.calculate_measurement(
                geom=geom,
                source_crs=source_crs,
            )

            feature_data = {
                "feature_index": int(idx),
                "geometry_type": geom_type,
                "crs": crs_str,
                "properties": clean_props,
                "measurement_type": measurement.type if measurement else None,
                "measurement_value": measurement.value if measurement else None,
                "measurement_unit": measurement.unit if measurement else None,
                "measurement_status": status.value,
            }
            features.append(feature_data)

        return features
