"""Input validation, mime-type verification, and file extension checks."""

import io
import zipfile
from fastapi.testclient import TestClient
from tests.fixtures.sample_generators import create_shapefile_zip_bytes


def test_upload_unsupported_extensions(client: TestClient) -> None:
    """Verify that unsupported extensions (.geojson, .txt, .csv, .exe) return 400."""
    unsupported_cases = [
        ("data.geojson", b'{"type": "FeatureCollection", "features": []}'),
        ("data.txt", b"plain text content"),
        ("data.csv", b"lat,lon\n10,20\n"),
        ("evil.exe", b"MZ\x90\x00\x03\x00\x00\x00"),
        ("archive.tar.gz", b"\x1f\x8b\x08\x00"),
    ]

    for filename, content in unsupported_cases:
        files = {"file": (filename, content, "application/octet-stream")}
        response = client.post("/api/files/", files=files)
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] in ("INVALID_FILE", "UNSUPPORTED_FORMAT")


def test_upload_file_without_extension(client: TestClient) -> None:
    """Verify that uploading a file with no extension returns 400."""
    files = {"file": ("mygeodata", b"some raw data", "application/octet-stream")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_FILE"


def test_upload_empty_file_rejected(client: TestClient) -> None:
    """Verify that an empty (0 byte) file is rejected with HTTP 400."""
    files = {"file": ("empty.kml", b"", "application/vnd.google-earth.kml+xml")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] in ("EMPTY_FILE", "INVALID_FILE")


def test_upload_magic_bytes_spoofing_kml(client: TestClient) -> None:
    """Verify that a binary non-XML file renamed to .kml is rejected by magic byte inspection."""
    fake_kml = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08BINARY_JUNK_PAYLOAD"
    files = {"file": ("fake.kml", fake_kml, "application/vnd.google-earth.kml+xml")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_FILE"


def test_upload_magic_bytes_spoofing_zip(client: TestClient) -> None:
    """Verify that a text file renamed to .zip is rejected by PK header magic byte inspection."""
    fake_zip = b"Hello, this is just a plain text document pretending to be a zip."
    files = {"file": ("fake.zip", fake_zip, "application/zip")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_FILE"


def test_upload_corrupt_zip_archive(client: TestClient) -> None:
    """Verify that a damaged/corrupt ZIP archive returns HTTP 400."""
    corrupt_zip_bytes = create_shapefile_zip_bytes(corrupt_zip=True)
    files = {"file": ("corrupt.zip", corrupt_zip_bytes, "application/zip")}

    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] in ("INVALID_ZIP_ARCHIVE", "INVALID_FILE")


def test_upload_empty_zip_archive(client: TestClient) -> None:
    """Verify that a valid ZIP archive containing 0 entries is rejected with HTTP 400."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        pass  # No entries written
    buffer.seek(0)

    files = {"file": ("empty_archive.zip", buffer.getvalue(), "application/zip")}
    response = client.post("/api/files/", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_FILE"
    assert "empty" in data["error"]["message"].lower()


def test_upload_missing_file_payload(client: TestClient) -> None:
    """Verify that POST without the 'file' field returns HTTP 422."""
    response = client.post("/api/files/", data={"not_file": "test"})
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] in ("VALIDATION_ERROR", "UNPROCESSABLE_ENTITY")
