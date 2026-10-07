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
      <description>Commercial Property</description>
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
      <description>Primary Access Road</description>
      <LineString>
        <coordinates>{line_str}</coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Survey Station</name>
      <description>GPS Benchmark Point</description>
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
    subfolder: Optional[str] = None,
    include_macos_metadata: bool = False,
) -> bytes:
    """Programmatically generate an in-memory Shapefile ZIP archive.

    Supports generating valid shapefiles, missing CRS, missing companion files,
    nested folders, macOS metadata entries, path traversal payloads, and corrupt zip bytes.
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
            prefix = f"{subfolder}/" if subfolder else ""
            for f in temp_dir.glob("test_layer.*"):
                ext = f.suffix.lower()

                # Skip prj if explicitly testing missing CRS
                if ext == ".prj" and not include_prj:
                    continue

                # Skip requested extensions (e.g. .shx or .dbf)
                if omit_extensions and ext in omit_extensions:
                    continue

                zf.write(f, arcname=f"{prefix}{f.name}")

            if include_macos_metadata:
                zf.writestr("__MACOSX/._test_layer.shp", b"MAC_RESOURCE_FORK_METADATA")

            if include_traversal_member:
                # Malicious zip slip entry
                zf.writestr(include_traversal_member, b"MALICIOUS_PAYLOAD")

    buffer.seek(0)
    return buffer.getvalue()


def create_multi_shapefile_zip_bytes() -> bytes:
    """Generate a ZIP archive containing multiple conflicting Shapefile datasets."""
    poly1 = Polygon([(10.0, 50.0), (10.01, 50.0), (10.01, 50.01), (10.0, 50.01), (10.0, 50.0)])
    gdf1 = gpd.GeoDataFrame([{"name": "Layer 1"}], geometry=[poly1], crs="EPSG:4326")

    poly2 = Polygon([(20.0, 60.0), (20.01, 60.0), (20.01, 60.01), (20.0, 60.01), (20.0, 60.0)])
    gdf2 = gpd.GeoDataFrame([{"name": "Layer 2"}], geometry=[poly2], crs="EPSG:4326")

    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        shp1 = temp_dir / "parcels.shp"
        shp2 = temp_dir / "buildings.shp"

        gdf1.to_file(shp1, driver="ESRI Shapefile", engine="pyogrio")
        gdf2.to_file(shp2, driver="ESRI Shapefile", engine="pyogrio")

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in temp_dir.glob("parcels.*"):
                zf.write(f, arcname=f.name)
            for f in temp_dir.glob("buildings.*"):
                zf.write(f, arcname=f.name)

    buffer.seek(0)
    return buffer.getvalue()


def create_zip_with_many_files(count: int = 1005) -> bytes:
    """Generate a ZIP archive with excessive entry count to test decompression bomb defense."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(count):
            zf.writestr(f"file_{i}.txt", b"x")
    buffer.seek(0)
    return buffer.getvalue()
