"""Tests verifying consistent structured error responses, status codes, and exception envelopes."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from tests.fixtures.sample_generators import create_shapefile_zip_bytes


def test_error_envelope_structure_on_404(client: TestClient) -> None:
    """Verify that a 404 response strictly contains the unified error envelope."""
    response = client.get("/api/files/00000000-0000-0000-0000-000000000000/")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "FILE_NOT_FOUND"
    assert "message" in data["error"]
    assert "00000000-0000-0000-0000-000000000000" in data["error"]["message"]


def test_error_envelope_structure_on_measurements_404(client: TestClient) -> None:
    """Verify that a 404 response on measurements route conforms to error envelope."""
    response = client.get("/api/files/ffffffff-ffff-ffff-ffff-ffffffffffff/measurements/")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "FILE_NOT_FOUND"


def test_error_envelope_structure_on_400(client: TestClient) -> None:
    """Verify that a 400 response from invalid extension conforms to error envelope."""
    files = {"file": ("data.xyz", b"unsupported", "application/octet-stream")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] in ("INVALID_FILE", "UNSUPPORTED_FORMAT")
    assert isinstance(data["error"]["message"], str)


def test_error_envelope_structure_on_422_missing_crs(client: TestClient) -> None:
    """Verify that a 422 response from missing CRS conforms to error envelope."""
    zip_bytes = create_shapefile_zip_bytes(include_prj=False)
    files = {"file": ("no_prj.zip", zip_bytes, "application/zip")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "MISSING_CRS"
    assert "prj" in data["error"]["message"].lower()


def test_error_envelope_structure_on_422_validation_error(client: TestClient) -> None:
    """Verify that FastAPI request validation errors are wrapped in standard error envelope."""
    response = client.post("/api/files/", data={"not_file": "missing file field"})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] in ("VALIDATION_ERROR", "UNPROCESSABLE_ENTITY")
    assert "message" in data["error"]


def test_error_envelope_structure_on_413(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that 413 File Too Large responses conform to error envelope."""
    monkeypatch.setattr(type(settings), "max_upload_size_bytes", property(lambda self: 50))
    files = {"file": ("big.kml", b"X" * 100, "application/vnd.google-earth.kml+xml")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 413
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "FILE_TOO_LARGE"


def test_undefined_route_returns_404(client: TestClient) -> None:
    """Verify that accessing an unregistered route returns HTTP 404."""
    response = client.get("/api/nonexistent/endpoint/")
    assert response.status_code == 404
