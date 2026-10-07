"""Tests for GET /api/files/{id}/measurements/ endpoint and geometry calculations."""

from fastapi.testclient import TestClient
import pyproj
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from app.schemas.common import MeasurementStatus
from app.services.measurement_service import MeasurementService
from tests.fixtures.sample_generators import (
    create_sample_kml_bytes,
    create_shapefile_zip_bytes,
)


def test_get_measurements_success(client: TestClient) -> None:
    """Verify measurement retrieval for an uploaded dataset."""
    kml_bytes = create_sample_kml_bytes()
    file_id = client.post("/api/files/", files={"file": ("survey.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}).json()["id"]

    response = client.get(f"/api/files/{file_id}/measurements/")
    assert response.status_code == 200
    data = response.json()

    assert data["file_id"] == file_id
    features = data["features"]
    assert len(features) == 3

    # Feature 0: Polygon
    assert features[0]["feature_id"] == 0
    assert features[0]["geometry_type"] == "Polygon"
    assert features[0]["measurement"]["type"] == "area"
    assert features[0]["measurement"]["unit"] == "m²"
    assert features[0]["measurement"]["value"] > 0
    assert features[0]["measurement_status"] == "COMPLETED"

    # Feature 1: LineString
    assert features[1]["feature_id"] == 1
    assert features[1]["geometry_type"] == "LineString"
    assert features[1]["measurement"]["type"] == "length"
    assert features[1]["measurement"]["unit"] == "m"
    assert features[1]["measurement"]["value"] > 0
    assert features[1]["measurement_status"] == "COMPLETED"

    # Feature 2: Point
    assert features[2]["feature_id"] == 2
    assert features[2]["geometry_type"] == "Point"
    assert features[2]["measurement"] is None
    assert features[2]["measurement_status"] == "COMPLETED"


def test_multipolygon_measurement(client: TestClient) -> None:
    """Verify MultiPolygon total area calculation."""
    poly1 = Polygon([(10.0, 50.0), (10.01, 50.0), (10.01, 50.01), (10.0, 50.01), (10.0, 50.0)])
    poly2 = Polygon([(10.02, 50.0), (10.03, 50.0), (10.03, 50.01), (10.02, 50.01), (10.02, 50.0)])
    multi_poly = MultiPolygon([poly1, poly2])

    zip_bytes = create_shapefile_zip_bytes(geometries=[multi_poly], properties=[{"name": "Multi Island"}])
    file_id = client.post("/api/files/", files={"file": ("multi_poly.zip", zip_bytes, "application/zip")}).json()["id"]

    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    features = meas_res.json()["features"]
    assert features[0]["geometry_type"] == "MultiPolygon"
    assert features[0]["measurement"]["type"] == "area"
    assert features[0]["measurement"]["unit"] == "m²"
    assert features[0]["measurement"]["value"] > 1_000_000.0


def test_multilinestring_measurement(client: TestClient) -> None:
    """Verify MultiLineString total length calculation."""
    line1 = LineString([(10.0, 50.0), (10.01, 50.0)])
    line2 = LineString([(10.01, 50.0), (10.02, 50.0)])
    multi_line = MultiLineString([line1, line2])

    zip_bytes = create_shapefile_zip_bytes(geometries=[multi_line], properties=[{"name": "Multi Road"}])
    file_id = client.post("/api/files/", files={"file": ("multi_line.zip", zip_bytes, "application/zip")}).json()["id"]

    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    features = meas_res.json()["features"]
    assert features[0]["geometry_type"] == "MultiLineString"
    assert features[0]["measurement"]["type"] == "length"
    assert features[0]["measurement"]["unit"] == "m"
    assert features[0]["measurement"]["value"] > 1400.0


def test_multipoint_measurement_handling() -> None:
    """Verify MultiPoint returns null measurement with COMPLETED status."""
    multi_pt = MultiPoint([(10.0, 50.0), (10.01, 50.01)])
    crs = pyproj.CRS.from_epsg(4326)

    meas, status = MeasurementService.calculate_measurement(multi_pt, crs)
    assert meas is None
    assert status == MeasurementStatus.COMPLETED


def test_unsupported_geometry_collection_handling() -> None:
    """Verify GeometryCollection returns null measurement and UNSUPPORTED status without crashing."""
    geom_col = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])
    crs = pyproj.CRS.from_epsg(4326)

    meas, status = MeasurementService.calculate_measurement(geom_col, crs)
    assert meas is None
    assert status == MeasurementStatus.UNSUPPORTED


def test_empty_geometry_handling() -> None:
    """Verify empty geometry returns null measurement with UNSUPPORTED status without crashing."""
    empty_poly = Polygon()
    crs = pyproj.CRS.from_epsg(4326)

    meas, status = MeasurementService.calculate_measurement(empty_poly, crs)
    assert meas is None
    assert status == MeasurementStatus.UNSUPPORTED


def test_get_measurements_nonexistent_id(client: TestClient) -> None:
    """Verify HTTP 404 when querying measurements for a nonexistent ID."""
    response = client.get("/api/files/00000000-0000-0000-0000-000000000000/measurements/")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "FILE_NOT_FOUND"


def test_get_measurements_trailing_and_non_trailing_slash(client: TestClient) -> None:
    """Verify GET measurements works with and without trailing slash."""
    kml_bytes = create_sample_kml_bytes()
    file_id = client.post("/api/files/", files={"file": ("test.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}).json()["id"]

    res_slash = client.get(f"/api/files/{file_id}/measurements/")
    assert res_slash.status_code == 200

    res_no_slash = client.get(f"/api/files/{file_id}/measurements")
    assert res_no_slash.status_code == 200
