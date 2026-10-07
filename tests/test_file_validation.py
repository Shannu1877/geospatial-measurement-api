"""Unit and integration tests for upload file validation and error handling."""

import io
import zipfile
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from tests.fixtures.sample_generators import create_shapefile_zip_bytes


def test_reject_unsupported_file_extension(client: TestClient) -> None:
    """Verify that uploading files with unsupported extensions is rejected with HTTP 400."""
    files = {"file": ("data.geojson", b'{"type": "FeatureCollection"}', "application/json")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_FILE"
    assert "Unsupported file format" in data["error"]["message"]


def test_reject_empty_file(client: TestClient) -> None:
    """Verify that uploading an empty file is rejected with HTTP 400."""
    files = {"file": ("empty.kml", b"", "application/vnd.google-earth.kml+xml")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_FILE"
    assert "empty" in data["error"]["message"]


def test_reject_malformed_zip(client: TestClient) -> None:
    """Verify that uploading a corrupt or malformed ZIP is rejected with HTTP 400."""
    corrupt_zip = create_shapefile_zip_bytes(corrupt_zip=True)
    files = {"file": ("bad.zip", corrupt_zip, "application/zip")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_FILE"
    assert "ZIP" in data["error"]["message"]


def test_reject_zip_without_shapefile(client: TestClient) -> None:
    """Verify that uploading a valid ZIP archive without a .shp file is rejected with HTTP 400."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "No shapefile here.")
    buf.seek(0)

    files = {"file": ("noshape.zip", buf.getvalue(), "application/zip")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_FILE"
    assert ".shp file not found" in data["error"]["message"]


def test_reject_zip_with_missing_companion_files(client: TestClient) -> None:
    """Verify that a shapefile missing mandatory .shx or .dbf companion files is rejected with HTTP 400."""
    # Omit .dbf
    zip_bytes = create_shapefile_zip_bytes(omit_extensions=[".dbf"])
    files = {"file": ("missing_dbf.zip", zip_bytes, "application/zip")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_FILE"
    assert "missing required companion file" in data["error"]["message"]


def test_file_size_validation(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that files exceeding MAX_UPLOAD_SIZE_MB trigger HTTP 413."""
    # Temporarily set max size to 1 MB for testing
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)

    oversized_data = b"PK\x03\x04" + b"0" * (1024 * 1024 + 100)  # > 1MB
    files = {"file": ("large.zip", oversized_data, "application/zip")}
    response = client.post("/api/files/", files=files)

    assert response.status_code == 413
    data = response.json()
    assert data["error"]["code"] == "FILE_TOO_LARGE"
