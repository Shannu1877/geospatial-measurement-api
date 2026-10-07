"""End-to-end integration tests for /api/files/ endpoints."""

from fastapi.testclient import TestClient
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
)

from tests.fixtures.sample_generators import (
    create_sample_kml_bytes,
    create_shapefile_zip_bytes,
)


def test_upload_valid_kml(client: TestClient) -> None:
    """Verify end-to-end upload and processing of a valid KML file."""
    kml_bytes = create_sample_kml_bytes()
    files = {"file": ("survey.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 200
    data = response.json()

    assert "id" in data
    assert data["filename"] == "survey.kml"
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 3
    assert data["crs"] == "EPSG:4326"

    # Query file info endpoint
    file_id = data["id"]
    info_res = client.get(f"/api/files/{file_id}/")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["id"] == file_id
    assert info_data["status"] == "COMPLETED"
    assert info_data["feature_count"] == 3

    # Query measurements endpoint
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["file_id"] == file_id
    features = meas_data["features"]
    assert len(features) == 3

    # Feature 0: Polygon
    feat_0 = features[0]
    assert feat_0["geometry_type"] == "Polygon"
    assert feat_0["measurement"]["type"] == "area"
    assert feat_0["measurement"]["unit"] == "m²"
    assert feat_0["measurement"]["value"] > 0

    # Feature 1: LineString
    feat_1 = features[1]
    assert feat_1["geometry_type"] == "LineString"
    assert feat_1["measurement"]["type"] == "length"
    assert feat_1["measurement"]["unit"] == "m"
    assert feat_1["measurement"]["value"] > 0

    # Feature 2: Point
    feat_2 = features[2]
    assert feat_2["geometry_type"] == "Point"
    assert feat_2["measurement"] is None
    assert feat_2["measurement_status"] == "COMPLETED"


def test_upload_valid_shapefile_zip(client: TestClient) -> None:
    """Verify end-to-end upload and processing of a valid Shapefile ZIP archive."""
    geoms = [
        Polygon([(10.0, 50.0), (10.01, 50.0), (10.01, 50.01), (10.0, 50.01), (10.0, 50.0)]),
        Polygon([(10.02, 50.0), (10.03, 50.0), (10.03, 50.01), (10.02, 50.01), (10.02, 50.0)]),
        Polygon([(10.04, 50.0), (10.05, 50.0), (10.05, 50.01), (10.04, 50.01), (10.04, 50.0)]),
    ]
    props = [{"name": "Plot A"}, {"name": "Plot B"}, {"name": "Plot C"}]
    zip_bytes = create_shapefile_zip_bytes(geometries=geoms, properties=props, crs="EPSG:4326")

    files = {"file": ("cadastre.zip", zip_bytes, "application/zip")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["filename"] == "cadastre.zip"
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 3
    assert data["crs"] == "EPSG:4326"

    # Verify measurements
    file_id = data["id"]
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    features = meas_res.json()["features"]

    for feat in features:
        assert feat["geometry_type"] == "Polygon"
        assert feat["measurement"]["type"] == "area"
        assert feat["measurement"]["unit"] == "m²"
        assert feat["measurement"]["value"] > 500000


def test_file_not_found_returns_404(client: TestClient) -> None:
    """Verify that querying a nonexistent file ID returns HTTP 404."""
    response = client.get("/api/files/nonexistent-uuid-12345/")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "FILE_NOT_FOUND"

    meas_res = client.get("/api/files/nonexistent-uuid-12345/measurements/")
    assert meas_res.status_code == 404
    assert meas_res.json()["error"]["code"] == "FILE_NOT_FOUND"


def test_missing_crs_rejected_with_422(client: TestClient) -> None:
    """Verify that a Shapefile without .prj (missing CRS) is rejected with HTTP 422."""
    zip_bytes = create_shapefile_zip_bytes(include_prj=False)
    files = {"file": ("no_crs.zip", zip_bytes, "application/zip")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "MISSING_CRS"
    assert "Coordinate Reference System" in data["error"]["message"]


def test_corrupt_geospatial_file_rejected_with_422(client: TestClient) -> None:
    """Verify that a syntactically invalid/unparseable KML is rejected with HTTP 422."""
    corrupt_kml = b"<?xml version='1.0'?><kml><Placemark><Polygon>CORRUPTED_XML</kml>"
    files = {"file": ("corrupt.kml", corrupt_kml, "application/vnd.google-earth.kml+xml")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "CORRUPT_GEOSPATIAL_FILE"


def test_multipolygon_and_multilinestring_api(client: TestClient) -> None:
    """Verify API correctly processes MultiPolygon and MultiLineString geometries."""
    # 1. MultiPolygon shapefile
    poly1 = Polygon([(10.0, 50.0), (10.01, 50.0), (10.01, 50.01), (10.0, 50.01), (10.0, 50.0)])
    poly2 = Polygon([(10.02, 50.0), (10.03, 50.0), (10.03, 50.01), (10.02, 50.01), (10.02, 50.0)])
    multi_poly = MultiPolygon([poly1, poly2])

    zip_bytes_poly = create_shapefile_zip_bytes(
        geometries=[multi_poly],
        properties=[{"name": "Multi Island"}],
        crs="EPSG:4326",
    )
    res_poly = client.post("/api/files/", files={"file": ("multi_poly.zip", zip_bytes_poly, "application/zip")})
    assert res_poly.status_code == 200
    poly_id = res_poly.json()["id"]

    meas_poly = client.get(f"/api/files/{poly_id}/measurements/").json()["features"]
    assert meas_poly[0]["geometry_type"] == "MultiPolygon"
    assert meas_poly[0]["measurement"]["type"] == "area"
    assert meas_poly[0]["measurement"]["unit"] == "m²"
    assert meas_poly[0]["measurement"]["value"] > 1000000

    # 2. MultiLineString shapefile
    line1 = LineString([(10.0, 50.0), (10.01, 50.0)])
    line2 = LineString([(10.01, 50.0), (10.02, 50.0)])
    multi_line = MultiLineString([line1, line2])

    zip_bytes_line = create_shapefile_zip_bytes(
        geometries=[multi_line],
        properties=[{"name": "Multi Highway"}],
        crs="EPSG:4326",
    )
    res_line = client.post("/api/files/", files={"file": ("multi_line.zip", zip_bytes_line, "application/zip")})
    assert res_line.status_code == 200
    line_id = res_line.json()["id"]

    meas_line = client.get(f"/api/files/{line_id}/measurements/").json()["features"]
    assert meas_line[0]["geometry_type"] == "MultiLineString"
    assert meas_line[0]["measurement"]["type"] == "length"
    assert meas_line[0]["measurement"]["unit"] == "m"
    assert meas_line[0]["measurement"]["value"] > 1400


def test_trailing_and_non_trailing_slash_routes(client: TestClient) -> None:
    """Ensure routes are reachable both with and without trailing slash."""
    kml_bytes = create_sample_kml_bytes()
    files = {"file": ("survey_slash.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}

    # POST without trailing slash
    res_no_slash = client.post("/api/files", files=files)
    assert res_no_slash.status_code == 200
    file_id = res_no_slash.json()["id"]

    # GET info without trailing slash
    info_no_slash = client.get(f"/api/files/{file_id}")
    assert info_no_slash.status_code == 200

    # GET measurements without trailing slash
    meas_no_slash = client.get(f"/api/files/{file_id}/measurements")
    assert meas_no_slash.status_code == 200
