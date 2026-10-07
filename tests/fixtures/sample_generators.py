"""Programmatic geospatial fixture generators for automated testing."""

import io
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import geopandas as gpd
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)


def create_sample_kml_bytes(
    polygon_coords: Optional[List[tuple]] = None,
    linestring_coords: Optional[List[tuple]] = None,
    point_coord: Optional[tuple] = None,
) -> bytes:
    """Generate in-memory valid KML file content."""
    poly_coords = polygon_coords or [
        (-122.0822, 37.4222),
        (-122.0822, 37.4214),
        (-122.0810, 37.4214),
        (-122.0810, 37.4222),
        (-122.0822, 37.4222),
    ]
    poly_str = " ".join(f"{lon},{lat},0" for lon, lat in poly_coords)

    line_coords = linestring_coords or [
        (-122.0822, 37.4222),
        (-122.0810, 37.4214),
    ]
    line_str = " ".join(f"{lon},{lat},0" for lon, lat in line_coords)

    pt_coord = point_coord or (-122.0822, 37.4222)
    pt_str = f"{pt_coord[0]},{pt_coord[1]},0"

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Test Survey Dataset</name>
    <Placemark>
      <name>Building A</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>{poly_str}</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Road 1</name>
      <LineString>
        <coordinates>{line_str}</coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Survey Station</name>
      <Point>
        <coordinates>{pt_str}</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>"""
    return kml.encode("utf-8")


def create_shapefile_zip_bytes(
    geometries: Optional[List[Any]] = None,
    properties: Optional[List[Dict[str, Any]]] = None,
    crs: Optional[str] = "EPSG:4326",
    include_prj: bool = True,
    omit_extensions: Optional[List[str]] = None,
    corrupt_zip: bool = False,
    include_traversal_member: Optional[str] = None,
) -> bytes:
    """Programmatically generate an in-memory Shapefile ZIP archive.

    Supports generating valid shapefiles, missing CRS, missing companion files,
    path traversal payloads, and corrupt zip bytes.
    """
    if corrupt_zip:
        return b"PK\x03\x04" + b"CORRUPTED_ZIP_BINARY_DATA_PAYLOAD_HERE"

    geoms = geometries or [
        Polygon([(10.0, 50.0), (10.01, 50.0), (10.01, 50.01), (10.0, 50.01), (10.0, 50.0)]),
        Polygon([(10.02, 50.0), (10.03, 50.0), (10.03, 50.01), (10.02, 50.01), (10.02, 50.0)]),
        Polygon([(10.04, 50.0), (10.05, 50.0), (10.05, 50.01), (10.04, 50.01), (10.04, 50.0)]),
    ]

    props = properties or [{"name": f"Feature {i}"} for i in range(len(geoms))]

    gdf = gpd.GeoDataFrame(props, geometry=geoms, crs=crs)

    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        shp_file = temp_dir / "test_layer.shp"

        # Pyogrio / GDAL export to shapefile
        gdf.to_file(shp_file, driver="ESRI Shapefile", engine="pyogrio")

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in temp_dir.glob("test_layer.*"):
                ext = f.suffix.lower()

                # Skip prj if explicitly testing missing CRS
                if ext == ".prj" and not include_prj:
                    continue

                # Skip requested extensions (e.g. .shx or .dbf)
                if omit_extensions and ext in omit_extensions:
                    continue

                zf.write(f, arcname=f.name)

            if include_traversal_member:
                # Malicious zip slip entry
                zf.writestr(include_traversal_member, b"MALICIOUS_PAYLOAD")

    buffer.seek(0)
    return buffer.getvalue()
