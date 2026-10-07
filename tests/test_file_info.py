"""Tests for GET /api/files/{id}/ file information endpoint."""

from fastapi.testclient import TestClient

from tests.fixtures.sample_generators import (
    create_sample_kml_bytes,
    create_shapefile_zip_bytes,
)


def test_get_file_info_success(client: TestClient) -> None:
    """Verify metadata retrieval for a successfully processed file."""
    kml_bytes = create_sample_kml_bytes()
    upload_res = client.post("/api/files/", files={"file": ("survey.kml", kml_bytes, "application/vnd.google-earth.kml+xml")})
    file_id = upload_res.json()["id"]

    response = client.get(f"/api/files/{file_id}/")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == file_id
    assert data["filename"] == "survey.kml"
    assert data["feature_count"] == 3
    assert data["crs"] == "EPSG:4326"
    assert data["status"] == "COMPLETED"
    assert data["file_size_bytes"] > 0
    assert data["error_message"] is None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_get_file_info_trailing_and_non_trailing_slash(client: TestClient) -> None:
    """Verify GET works with and without trailing slash."""
    kml_bytes = create_sample_kml_bytes()
    file_id = client.post("/api/files/", files={"file": ("test.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}).json()["id"]

    res_slash = client.get(f"/api/files/{file_id}/")
    assert res_slash.status_code == 200

    res_no_slash = client.get(f"/api/files/{file_id}")
    assert res_no_slash.status_code == 200


def test_get_file_info_nonexistent_id(client: TestClient) -> None:
    """Verify HTTP 404 on nonexistent file ID."""
    response = client.get("/api/files/00000000-0000-0000-0000-000000000000/")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "FILE_NOT_FOUND"


def test_get_file_info_malformed_id(client: TestClient) -> None:
    """Verify HTTP 404 on malformed ID string."""
    response = client.get("/api/files/not-a-valid-uuid-!@#$%^/")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "FILE_NOT_FOUND"


def test_get_file_info_failed_processing_record(client: TestClient) -> None:
    """Verify that a failed processing run persists status FAILED and error message in DB."""
    # Shapefile missing CRS will fail during processing
    no_crs_zip = create_shapefile_zip_bytes(include_prj=False)
    upload_res = client.post("/api/files/", files={"file": ("no_crs.zip", no_crs_zip, "application/zip")})
    assert upload_res.status_code == 422

    # Query the created file record directly to ensure failed state is recorded
    # We retrieve the file ID from the database
    from app.db.database import get_db
    from app.db.models import FileRecord

    db = next(client.app.dependency_overrides[get_db]())
    failed_record = db.query(FileRecord).filter(FileRecord.filename == "no_crs.zip").first()
    assert failed_record is not None
    assert failed_record.status == "FAILED"
    assert "Coordinate Reference System" in failed_record.error_message

    info_res = client.get(f"/api/files/{failed_record.id}/")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["status"] == "FAILED"
    assert "Coordinate Reference System" in info_data["error_message"]
