"""Comprehensive tests for ESRI Shapefile ZIP ingestion, validation, and measurement."""

from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, Polygon
from tests.fixtures.sample_generators import (
    create_multi_shapefile_zip_bytes,
    create_shapefile_zip_bytes,
)


def test_shapefile_zip_polygon_area_calculation(client: TestClient) -> None:
    """Verify that a Shapefile with polygons returns metric area measurements."""
    polys = [
        Polygon([(10.0, 50.0), (10.01, 50.0), (10.01, 50.01), (10.0, 50.01), (10.0, 50.0)])
    ]
    zip_bytes = create_shapefile_zip_bytes(geometries=polys, crs="EPSG:4326")
    files = {"file": ("polygons.zip", zip_bytes, "application/zip")}

    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    features = meas_resp.json()["features"]
    assert len(features) == 1
    assert features[0]["geometry_type"] == "Polygon"
    assert features[0]["measurement"]["type"] == "area"
    assert features[0]["measurement"]["unit"] == "m²"
    assert features[0]["measurement"]["value"] > 0


def test_shapefile_zip_linestring_length_calculation(client: TestClient) -> None:
    """Verify that a Shapefile with LineStrings returns metric length measurements."""
    lines = [
        LineString([(10.0, 50.0), (10.01, 50.01)]),
        LineString([(10.01, 50.01), (10.02, 50.02)]),
    ]
    zip_bytes = create_shapefile_zip_bytes(geometries=lines, crs="EPSG:4326")
    files = {"file": ("lines.zip", zip_bytes, "application/zip")}

    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    features = meas_resp.json()["features"]
    assert len(features) == 2
    for feat in features:
        assert feat["geometry_type"] == "LineString"
        assert feat["measurement"]["type"] == "length"
        assert feat["measurement"]["unit"] == "m"
        assert feat["measurement"]["value"] > 0


def test_shapefile_zip_points_null_measurement(client: TestClient) -> None:
    """Verify that a Shapefile with Points produces null measurements."""
    points = [Point(10.0, 50.0), Point(10.01, 50.01)]
    zip_bytes = create_shapefile_zip_bytes(geometries=points, crs="EPSG:4326")
    files = {"file": ("points.zip", zip_bytes, "application/zip")}

    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 200
    file_id = resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    features = meas_resp.json()["features"]
    assert len(features) == 2
    for feat in features:
        assert feat["geometry_type"] == "Point"
        assert feat["measurement"] is None
        assert feat["measurement_status"] == "COMPLETED"


def test_shapefile_missing_prj_rejected(client: TestClient) -> None:
    """Verify that a Shapefile without a .prj file returns 422 MISSING_CRS."""
    zip_bytes = create_shapefile_zip_bytes(include_prj=False)
    files = {"file": ("no_prj.zip", zip_bytes, "application/zip")}

    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "MISSING_CRS"
    assert "prj" in data["error"]["message"].lower()


def test_shapefile_missing_shx_rejected(client: TestClient) -> None:
    """Verify that a Shapefile missing .shx file is rejected with 400."""
    zip_bytes = create_shapefile_zip_bytes(omit_extensions=[".shx"])
    files = {"file": ("no_shx.zip", zip_bytes, "application/zip")}

    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["code"] == "INVALID_FILE"
    assert ".shx" in data["error"]["message"].lower()


def test_shapefile_missing_dbf_rejected(client: TestClient) -> None:
    """Verify that a Shapefile missing .dbf file is rejected with 400."""
    zip_bytes = create_shapefile_zip_bytes(omit_extensions=[".dbf"])
    files = {"file": ("no_dbf.zip", zip_bytes, "application/zip")}

    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["code"] == "INVALID_FILE"
    assert ".dbf" in data["error"]["message"].lower()


def test_shapefile_nested_in_subfolder(client: TestClient) -> None:
    """Verify that shapefiles nested in archive subdirectories are properly located and parsed."""
    zip_bytes = create_shapefile_zip_bytes(subfolder="deep/nested/directory/structure")
    files = {"file": ("nested.zip", zip_bytes, "application/zip")}

    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 200
    assert resp.json()["feature_count"] == 3
    assert resp.json()["status"] == "COMPLETED"


def test_shapefile_macos_metadata_ignored(client: TestClient) -> None:
    """Verify that macOS __MACOSX resource fork files do not trigger multiple-shapefile errors."""
    zip_bytes = create_shapefile_zip_bytes(include_macos_metadata=True)
    files = {"file": ("from_mac.zip", zip_bytes, "application/zip")}

    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"


def test_shapefile_multiple_shapefiles_rejected(client: TestClient) -> None:
    """Verify that a ZIP containing multiple conflicting Shapefiles is rejected with 400."""
    zip_bytes = create_multi_shapefile_zip_bytes()
    files = {"file": ("two_layers.zip", zip_bytes, "application/zip")}

    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["code"] == "INVALID_FILE"
    assert "multiple shapefile" in data["error"]["message"].lower()


def test_shapefile_zip_without_shp_rejected(client: TestClient) -> None:
    """Verify that a ZIP archive without any .shp file is rejected with 400."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("notes.txt", b"Just some notes, no shapefile here.")
    buffer.seek(0)

    files = {"file": ("no_shp.zip", buffer.getvalue(), "application/zip")}
    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["code"] == "INVALID_FILE"
    assert "shapefile" in data["error"]["message"].lower()


def test_shapefile_uppercase_extension(client: TestClient) -> None:
    """Verify that .ZIP in uppercase is accepted and processed successfully."""
    zip_bytes = create_shapefile_zip_bytes()
    files = {"file": ("SURVEY_DATA.ZIP", zip_bytes, "application/zip")}

    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 200
    assert resp.json()["filename"] == "SURVEY_DATA.ZIP"
    assert resp.json()["status"] == "COMPLETED"
