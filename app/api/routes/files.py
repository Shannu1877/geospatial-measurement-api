"""API routes for geospatial file upload, metadata retrieval, and feature measurements."""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.common import ErrorResponse
from app.schemas.file import FileInfoResponse, FileUploadResponse
from app.schemas.measurement import FileMeasurementsResponse
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Files & Measurements"])


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and Process Geospatial File",
    description=(
        "Accepts a KML (.kml) file or ESRI Shapefile ZIP (.zip) archive via multipart/form-data. "
        "Validates the file, extracts geographic features, detects the source CRS, calculates "
        "measurements (area in m² for polygons, length in m for linestrings), and records results."
    ),
    responses={
        200: {"model": FileUploadResponse, "description": "File successfully uploaded and processed"},
        400: {"model": ErrorResponse, "description": "Invalid file format, empty file, or security violation"},
        413: {"model": ErrorResponse, "description": "File size exceeds upload limit"},
        422: {"model": ErrorResponse, "description": "Corrupt or unparseable geospatial file, or missing CRS"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
@router.post("", response_model=FileUploadResponse, include_in_schema=False)
async def upload_file(
    file: UploadFile = File(..., description="Geospatial file (.kml or .zip Shapefile)"),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    """Upload and process a geospatial file."""
    # 1. Stream upload safely with validation
    file_id, stored_path, ext, file_size = await FileService.save_and_validate_upload(file)

    # 2. Create initial database record with PROCESSING state
    from app.utils.file_utils import sanitize_filename
    clean_filename = sanitize_filename(file.filename or "unknown")

    file_record = FileService.create_initial_file_record(
        file_id=file_id,
        filename=clean_filename,
        stored_path=stored_path,
        file_size_bytes=file_size,
        db=db,
    )

    # 3. Process geospatial dataset through measurement pipeline
    processed_record = FileService.process_file_pipeline(
        file_record=file_record,
        extension=ext,
        db=db,
    )

    return FileUploadResponse(
        id=processed_record.id,
        filename=processed_record.filename,
        feature_count=processed_record.feature_count,
        crs=processed_record.crs,
        status=processed_record.status,
    )


@router.get(
    "/{id}/",
    response_model=FileInfoResponse,
    summary="Get File Metadata",
    description="Retrieve processing status, feature count, detected CRS, and metadata for a previously uploaded file.",
    responses={
        200: {"model": FileInfoResponse, "description": "File metadata retrieved"},
        404: {"model": ErrorResponse, "description": "File not found"},
    },
)
@router.get("/{id}", response_model=FileInfoResponse, include_in_schema=False)
def get_file_info(
    id: str,
    db: Session = Depends(get_db),
) -> FileInfoResponse:
    """Get metadata for an uploaded file by ID."""
    file_record = FileService.get_file_record(id, db)

    return FileInfoResponse(
        id=file_record.id,
        filename=file_record.filename,
        feature_count=file_record.feature_count,
        crs=file_record.crs,
        status=file_record.status,
        file_size_bytes=file_record.file_size_bytes,
        error_message=file_record.error_message,
        created_at=file_record.created_at,
        updated_at=file_record.updated_at,
    )


@router.get(
    "/{id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get Feature Measurements",
    description="Retrieve computed metric measurements (area in m², length in m) and properties for every feature in the file.",
    responses={
        200: {"model": FileMeasurementsResponse, "description": "Feature measurements retrieved"},
        404: {"model": ErrorResponse, "description": "File not found"},
    },
)
@router.get("/{id}/measurements", response_model=FileMeasurementsResponse, include_in_schema=False)
def get_file_measurements(
    id: str,
    db: Session = Depends(get_db),
) -> FileMeasurementsResponse:
    """Get all feature measurements for an uploaded file by ID."""
    return FileService.get_file_measurements(id, db)
