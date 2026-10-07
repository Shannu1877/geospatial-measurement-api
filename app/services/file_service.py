"""File lifecycle management, upload validation, and workflow orchestration service."""

import uuid
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.models import FeatureMeasurementRecord, FileRecord
from app.exceptions.custom_exceptions import (
    CorruptGeospatialFileException,
    FileNotFoundException,
    FileTooLargeException,
    GeospatialAPIException,
    InvalidFileException,
    MissingCRSException,
)
from app.schemas.measurement import (
    FeatureMeasurementResponse,
    FileMeasurementsResponse,
    MeasurementItem,
)
from app.services.geospatial_service import GeospatialService
from app.utils.file_utils import (
    validate_file_content,
    validate_file_extension,
)

CHUNK_SIZE = 64 * 1024  # 64 KB read buffer


class FileService:
    """Orchestrates file storage, security checks, database recording, and processing."""

    @classmethod
    async def save_and_validate_upload(
        cls,
        upload_file: UploadFile,
    ) -> Tuple[str, Path, str, int]:
        """Stream uploaded file to disk with strict size, extension, and content verification.

        Returns:
            Tuple of (file_id, stored_path, normalized_extension, total_bytes).

        Raises:
            InvalidFileException: For bad extension, empty file, or content spoofing.
            FileTooLargeException: When byte count exceeds configured limit.
        """
        from app.utils.file_utils import sanitize_filename

        raw_filename = upload_file.filename or ""
        original_filename = sanitize_filename(raw_filename)
        ext = validate_file_extension(original_filename, settings.ALLOWED_EXTENSIONS)

        file_id = str(uuid.uuid4())
        stored_path = settings.upload_path / f"{file_id}{ext}"

        total_bytes = 0
        header_bytes = bytearray()
        max_bytes = settings.max_upload_size_bytes

        try:
            with open(stored_path, "wb") as out_file:
                while True:
                    chunk = await upload_file.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        out_file.close()
                        if stored_path.exists():
                            stored_path.unlink()
                        raise FileTooLargeException(
                            f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
                        )

                    # Accumulate first 1024 bytes for magic byte validation
                    if len(header_bytes) < 1024:
                        needed = 1024 - len(header_bytes)
                        header_bytes.extend(chunk[:needed])

                    out_file.write(chunk)

            # Check for empty file
            if total_bytes == 0:
                if stored_path.exists():
                    stored_path.unlink()
                raise InvalidFileException("Uploaded file is empty (0 bytes).")

            # Validate header magic bytes
            validate_file_content(bytes(header_bytes), ext)

            logger.info(
                "File uploaded successfully: ID=%s, filename='%s', size=%d bytes",
                file_id,
                original_filename,
                total_bytes,
            )
            return file_id, stored_path, ext, total_bytes

        except Exception:
            # Clean up partial on-disk file if any error occurred
            if stored_path.exists():
                stored_path.unlink()
            raise

    @classmethod
    def create_initial_file_record(
        cls,
        file_id: str,
        filename: str,
        stored_path: Path,
        file_size_bytes: int,
        db: Session,
    ) -> FileRecord:
        """Create and commit initial database record with status PROCESSING."""
        file_record = FileRecord(
            id=file_id,
            filename=filename,
            stored_path=str(stored_path),
            crs=None,
            feature_count=0,
            status="PROCESSING",
            file_size_bytes=file_size_bytes,
        )
        db.add(file_record)
        db.commit()
        db.refresh(file_record)
        return file_record

    @classmethod
    def process_file_pipeline(
        cls,
        file_record: FileRecord,
        extension: str,
        db: Session,
    ) -> FileRecord:
        """Execute full geospatial extraction and measurement pipeline.

        Updates database record to COMPLETED on success, or FAILED on error.
        """
        file_path = Path(file_record.stored_path)

        try:
            # 1. Read vector dataset and detect CRS
            gdf, crs_str = GeospatialService.read_geospatial_dataset(file_path, extension)

            # 2. CRS validation check: Missing CRS
            if crs_str is None:
                raise MissingCRSException(
                    "Missing Coordinate Reference System (CRS). ESRI Shapefile archives require a valid .prj file."
                )

            # 3. Process and measure features
            feature_dicts = GeospatialService.process_features(gdf, crs_str)

            # 4. Save features to database
            measurement_records = [
                FeatureMeasurementRecord(
                    file_id=file_record.id,
                    feature_index=f["feature_index"],
                    geometry_type=f["geometry_type"],
                    crs=f["crs"],
                    properties=f["properties"],
                    measurement_type=f["measurement_type"],
                    measurement_value=f["measurement_value"],
                    measurement_unit=f["measurement_unit"],
                    measurement_status=f["measurement_status"],
                )
                for f in feature_dicts
            ]
            db.add_all(measurement_records)

            # 5. Update file record to COMPLETED
            file_record.crs = crs_str
            file_record.feature_count = len(measurement_records)
            file_record.status = "COMPLETED"
            file_record.error_message = None
            db.commit()
            db.refresh(file_record)

            logger.info(
                "Completed processing file ID %s: %d features processed.",
                file_record.id,
                file_record.feature_count,
            )
            return file_record

        except GeospatialAPIException as exc:
            db.rollback()
            rec = db.query(FileRecord).filter(FileRecord.id == file_record.id).first()
            if rec:
                rec.status = "FAILED"
                rec.error_message = exc.message
                db.commit()
            logger.warning("File processing failed for ID %s: %s", file_record.id, exc.message)
            raise

        except Exception as exc:
            db.rollback()
            err_msg = f"Unexpected processing error: {str(exc)}"
            rec = db.query(FileRecord).filter(FileRecord.id == file_record.id).first()
            if rec:
                rec.status = "FAILED"
                rec.error_message = err_msg
                db.commit()
            logger.exception("Unexpected exception processing file ID %s", file_record.id)
            raise CorruptGeospatialFileException(err_msg) from exc

    @classmethod
    def get_file_record(cls, file_id: str, db: Session) -> FileRecord:
        """Retrieve file record by ID or raise FileNotFoundException."""
        record = db.query(FileRecord).filter(FileRecord.id == file_id).first()
        if not record:
            raise FileNotFoundException(f"Geospatial file with ID '{file_id}' not found.")
        return record

    @classmethod
    def get_file_measurements(cls, file_id: str, db: Session) -> FileMeasurementsResponse:
        """Retrieve all feature measurements for a given file ID."""
        file_record = cls.get_file_record(file_id, db)

        feature_records = (
            db.query(FeatureMeasurementRecord)
            .filter(FeatureMeasurementRecord.file_id == file_id)
            .order_by(FeatureMeasurementRecord.feature_index.asc())
            .all()
        )

        response_features = []
        for feat in feature_records:
            meas_item = None
            if feat.measurement_type and feat.measurement_value is not None:
                meas_item = MeasurementItem(
                    type=feat.measurement_type,
                    value=feat.measurement_value,
                    unit=feat.measurement_unit or "",
                )

            response_features.append(
                FeatureMeasurementResponse(
                    feature_id=feat.feature_index,
                    geometry_type=feat.geometry_type,
                    crs=feat.crs,
                    properties=feat.properties or {},
                    measurement=meas_item,
                    measurement_status=feat.measurement_status,
                )
            )

        return FileMeasurementsResponse(
            file_id=file_record.id,
            features=response_features,
        )
