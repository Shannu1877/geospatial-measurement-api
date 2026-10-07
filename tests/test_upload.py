"""Integration tests for POST /api/files/ upload endpoint."""

from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from tests.fixtures.sample_generators import (
    create_sample_kml_bytes,
    create_shapefile_zip_bytes,
)


def test_upload_valid_kml(client: TestClient) -> None:
    """Verify successful upload and processing of valid KML."""
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


def test_upload_valid_shapefile_zip(client: TestClient) -> None:
    """Verify successful upload and processing of valid Shapefile ZIP."""
    zip_bytes = create_shapefile_zip_bytes()
    files = {"file": ("boundary.zip", zip_bytes, "application/zip")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 200
    data = response.json()

    assert "id" in data
    assert data["filename"] == "boundary.zip"
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 3
    assert data["crs"] == "EPSG:4326"


def test_upload_uppercase_extensions(client: TestClient) -> None:
    """Verify that uppercase file extensions (.KML, .ZIP) are accepted and normalized."""
    # Uppercase .KML
    kml_bytes = create_sample_kml_bytes()
    res_kml = client.post("/api/files/", files={"file": ("CAPITAL.KML", kml_bytes, "application/vnd.google-earth.kml+xml")})
    assert res_kml.status_code == 200
    assert res_kml.json()["filename"] == "CAPITAL.KML"
    assert res_kml.json()["status"] == "COMPLETED"

    # Uppercase .ZIP
    zip_bytes = create_shapefile_zip_bytes()
    res_zip = client.post("/api/files/", files={"file": ("CAPITAL.ZIP", zip_bytes, "application/zip")})
    assert res_zip.status_code == 200
    assert res_zip.json()["filename"] == "CAPITAL.ZIP"
    assert res_zip.json()["status"] == "COMPLETED"


def test_upload_nested_subfolder_shapefile(client: TestClient) -> None:
    """Verify that a Shapefile nested inside an archive subfolder is successfully processed."""
    zip_bytes = create_shapefile_zip_bytes(subfolder="project_data/cadastre")
    files = {"file": ("nested.zip", zip_bytes, "application/zip")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 3


def test_upload_trailing_and_non_trailing_slash(client: TestClient) -> None:
    """Verify that POST works identically with or without trailing slash."""
    kml_bytes = create_sample_kml_bytes()

    res_slash = client.post("/api/files/", files={"file": ("slash.kml", kml_bytes, "application/vnd.google-earth.kml+xml")})
    assert res_slash.status_code == 200

    res_no_slash = client.post("/api/files", files={"file": ("noslash.kml", kml_bytes, "application/vnd.google-earth.kml+xml")})
    assert res_no_slash.status_code == 200
