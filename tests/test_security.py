"""Security tests verifying defense against path traversal, zip bombs, size limits, and info disclosure."""

import io
import zipfile
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from tests.fixtures.sample_generators import (
    create_sample_kml_bytes,
    create_shapefile_zip_bytes,
    create_zip_with_many_files,
)


def test_zip_path_traversal_relative_parent_rejected(client: TestClient) -> None:
    """Verify that a ZIP archive containing '../' traversal attempts is rejected."""
    malicious_zip = create_shapefile_zip_bytes(include_traversal_member="../../malicious.shp")
    files = {"file": ("exploit.zip", malicious_zip, "application/zip")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "SECURITY_VIOLATION"
    assert "path traversal" in data["error"]["message"].lower()


def test_zip_path_traversal_absolute_path_rejected(client: TestClient) -> None:
    """Verify that a ZIP archive containing absolute paths is rejected."""
    malicious_zip = create_shapefile_zip_bytes(include_traversal_member="/etc/shadow")
    files = {"file": ("exploit_abs.zip", malicious_zip, "application/zip")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "SECURITY_VIOLATION"


def test_zip_path_traversal_nested_relative_rejected(client: TestClient) -> None:
    """Verify that a ZIP archive containing nested parent directory 'sub/../../exploit.shp' is rejected."""
    malicious_zip = create_shapefile_zip_bytes(include_traversal_member="sub/../../exploit.shp")
    files = {"file": ("exploit_nested.zip", malicious_zip, "application/zip")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "SECURITY_VIOLATION"


def test_zip_windows_volume_indicator_rejected(client: TestClient) -> None:
    """Verify that a ZIP archive with Windows volume drive letters like 'C:exploit.shp' is rejected."""
    malicious_zip = create_shapefile_zip_bytes(include_traversal_member="C:exploit.shp")
    files = {"file": ("exploit_vol.zip", malicious_zip, "application/zip")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "SECURITY_VIOLATION"


def test_zip_bomb_excessive_entries_rejected(client: TestClient) -> None:
    """Verify that an archive containing more than 1000 entries triggers decompression bomb defense."""
    bomb_zip = create_zip_with_many_files(count=1005)
    files = {"file": ("bomb.zip", bomb_zip, "application/zip")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "SECURITY_VIOLATION"
    assert "too many entries" in data["error"]["message"].lower()


def test_filename_traversal_sanitization(client: TestClient) -> None:
    """Verify that malicious upload filenames with directory traversal are stripped to basenames."""
    kml_bytes = create_sample_kml_bytes()

    # Test unix-style path traversal filename
    files = {"file": ("../../../../etc/evil.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}
    resp = client.post("/api/files/", files=files)
    assert resp.status_code == 200
    assert ".." not in resp.json()["filename"]
    assert resp.json()["filename"] == "evil.kml"

    # Test windows-style path traversal filename
    files_win = {"file": ("..\\..\\windows\\system32\\win_evil.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}
    resp_win = client.post("/api/files/", files=files_win)
    assert resp_win.status_code == 200
    assert ".." not in resp_win.json()["filename"]
    assert "\\" not in resp_win.json()["filename"]
    assert resp_win.json()["filename"] == "win_evil.kml"


def test_file_size_exceeding_limit_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that uploads exceeding the configured maximum size are rejected with HTTP 413."""
    # Temporarily set max upload size to 100 bytes for boundary testing
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)
    monkeypatch.setattr(type(settings), "max_upload_size_bytes", property(lambda self: 100))

    oversized_data = b"X" * 150
    files = {"file": ("oversized.kml", oversized_data, "application/vnd.google-earth.kml+xml")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 413
    data = response.json()
    assert data["error"]["code"] == "FILE_TOO_LARGE"


def test_no_stack_traces_leaked_to_client(client: TestClient) -> None:
    """Ensure that error responses adhere strictly to the error envelope without tracebacks."""
    files = {"file": ("bad_kml.kml", b"<?xml version='1.0'?><kml><InvalidTag></kml>", "application/vnd.google-earth.kml+xml")}
    response = client.post("/api/files/", files=files)

    data = response.json()
    assert "Traceback" not in response.text
    assert 'File "' not in response.text
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
