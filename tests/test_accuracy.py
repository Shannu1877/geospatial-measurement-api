"""Mathematical accuracy and geometric ground-truth verification tests.

Validates that measurements match analytical expectations within standard tolerances:
- Projective area calculations match exact Euclidean area in projected CRS.
- Geographic EPSG:4326 coordinates are transformed to UTM, strictly avoiding degree-squared units.
- 3-4-5 right-triangle LineStrings yield exact Euclidean hypotenuse length.
- Multi-geometries accurately sum component areas/lengths.
- Self-intersecting polygons are repaired and measured accurately.
"""

import math
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from tests.fixtures.sample_generators import create_shapefile_zip_bytes


def test_analytical_square_area_in_projected_utm(client: TestClient) -> None:
    """Verify that a 100m x 100m square in UTM EPSG:32631 yields exactly 10,000.0 m²."""
    # UTM Zone 31N coordinates (meters)
    x0, y0 = 500000.0, 4000000.0
    square_100m = Polygon([
        (x0, y0),
        (x0 + 100.0, y0),
        (x0 + 100.0, y0 + 100.0),
        (x0, y0 + 100.0),
        (x0, y0),
    ])

    zip_bytes = create_shapefile_zip_bytes(geometries=[square_100m], crs="EPSG:32631")
    resp = client.post("/api/files/", files={"file": ("square_utm.zip", zip_bytes, "application/zip")})
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas = meas_resp.json()["features"][0]["measurement"]

    assert meas["type"] == "area"
    assert meas["unit"] == "m²"
    # Exact Euclidean area is 100 * 100 = 10,000 m²
    assert math.isclose(meas["value"], 10000.0, rel_tol=1e-4)


def test_epsg4326_polygon_does_not_return_degree_area(client: TestClient) -> None:
    """Verify that EPSG:4326 coordinates yield metric area (~12,000 m²) rather than degrees squared (1e-6)."""
    # 0.001 degrees at the equator (~111.3 meters per axis)
    square_deg = Polygon([
        (10.0, 0.0),
        (10.001, 0.0),
        (10.001, 0.001),
        (10.0, 0.001),
        (10.0, 0.0),
    ])

    zip_bytes = create_shapefile_zip_bytes(geometries=[square_deg], crs="EPSG:4326")
    resp = client.post("/api/files/", files={"file": ("square_deg.zip", zip_bytes, "application/zip")})
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas = meas_resp.json()["features"][0]["measurement"]

    assert meas["type"] == "area"
    assert meas["unit"] == "m²"

    # Degree area would be 1e-6 (0.000001). Metric area must be > 10,000 m²
    assert meas["value"] > 10000.0
    assert meas["value"] < 15000.0
    # Strict assertion that degree area was not returned
    assert meas["value"] != pytest.approx(1e-6)


def test_analytical_3_4_5_linestring_hypotenuse(client: TestClient) -> None:
    """Verify that a LineString with dx=300m, dy=400m in UTM yields exactly 500.0 meters."""
    x0, y0 = 500000.0, 4000000.0
    line_500m = LineString([
        (x0, y0),
        (x0 + 300.0, y0 + 400.0),
    ])

    zip_bytes = create_shapefile_zip_bytes(geometries=[line_500m], crs="EPSG:32631")
    resp = client.post("/api/files/", files={"file": ("line_500m.zip", zip_bytes, "application/zip")})
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas = meas_resp.json()["features"][0]["measurement"]

    assert meas["type"] == "length"
    assert meas["unit"] == "m"
    # Hypotenuse: sqrt(300^2 + 400^2) = 500.0
    assert math.isclose(meas["value"], 500.0, rel_tol=1e-4)


def test_multipolygon_additive_area(client: TestClient) -> None:
    """Verify that a MultiPolygon area equals the sum of its distinct component polygons."""
    x0, y0 = 500000.0, 4000000.0
    # Poly 1: 100m x 100m = 10,000 m²
    poly1 = Polygon([(x0, y0), (x0 + 100, y0), (x0 + 100, y0 + 100), (x0, y0 + 100), (x0, y0)])
    # Poly 2: 100m x 200m = 20,000 m²
    poly2 = Polygon([(x0 + 500, y0), (x0 + 700, y0), (x0 + 700, y0 + 100), (x0 + 500, y0 + 100), (x0 + 500, y0)])

    multipoly = MultiPolygon([poly1, poly2])

    zip_bytes = create_shapefile_zip_bytes(geometries=[multipoly], crs="EPSG:32631")
    resp = client.post("/api/files/", files={"file": ("multipoly.zip", zip_bytes, "application/zip")})
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas = meas_resp.json()["features"][0]["measurement"]

    assert meas["type"] == "area"
    assert math.isclose(meas["value"], 30000.0, rel_tol=1e-4)


def test_multilinestring_additive_length(client: TestClient) -> None:
    """Verify that a MultiLineString length equals the sum of its distinct component lines."""
    x0, y0 = 500000.0, 4000000.0
    line1 = LineString([(x0, y0), (x0 + 300.0, y0 + 400.0)])  # 500m
    line2 = LineString([(x0 + 1000.0, y0), (x0 + 1300.0, y0 + 400.0)])  # 500m

    multiline = MultiLineString([line1, line2])

    zip_bytes = create_shapefile_zip_bytes(geometries=[multiline], crs="EPSG:32631")
    resp = client.post("/api/files/", files={"file": ("multiline.zip", zip_bytes, "application/zip")})
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas = meas_resp.json()["features"][0]["measurement"]

    assert meas["type"] == "length"
    assert math.isclose(meas["value"], 1000.0, rel_tol=1e-4)


def test_self_intersecting_bowtie_polygon_repair(client: TestClient) -> None:
    """Verify that a self-intersecting bowtie polygon is repaired via make_valid and measured."""
    # Self-intersecting bowtie polygon: (0,0) -> (100,100) -> (100,0) -> (0,100) -> (0,0)
    x0, y0 = 500000.0, 4000000.0
    bowtie = Polygon([
        (x0, y0),
        (x0 + 100, y0 + 100),
        (x0 + 100, y0),
        (x0, y0 + 100),
        (x0, y0),
    ])

    zip_bytes = create_shapefile_zip_bytes(geometries=[bowtie], crs="EPSG:32631")
    resp = client.post("/api/files/", files={"file": ("bowtie.zip", zip_bytes, "application/zip")})
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas = meas_resp.json()["features"][0]["measurement"]

    # Two triangles of 50 x 50 / 2 * 2 = 5000 m²
    assert meas["type"] == "area"
    assert meas["value"] > 0
    assert math.isclose(meas["value"], 5000.0, rel_tol=1e-2)
