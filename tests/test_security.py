"""Security tests verifying defense against path traversal and info disclosure."""

from fastapi.testclient import TestClient
from tests.fixtures.sample_generators import create_shapefile_zip_bytes


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


def test_no_stack_traces_leaked_to_client(client: TestClient) -> None:
    """Ensure that error responses adhere strictly to the error envelope without tracebacks."""
    files = {"file": ("bad_kml.kml", b"<?xml version='1.0'?><kml><InvalidTag></kml>", "application/vnd.google-earth.kml+xml")}
    response = client.post("/api/files/", files=files)

    data = response.json()
    assert "Traceback" not in response.text
    assert "File \"" not in response.text
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
