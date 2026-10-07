"""SQLAlchemy database models for files and geospatial measurements."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class FileRecord(Base):
    """Stores metadata and processing status for an uploaded geospatial file."""

    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    stored_path = Column(String(1024), nullable=False)
    crs = Column(String(100), nullable=True)
    feature_count = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="PROCESSING")  # PROCESSING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    features = relationship(
        "FeatureMeasurementRecord",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FeatureMeasurementRecord.feature_index",
    )

    def __repr__(self) -> str:
        return f"<FileRecord(id='{self.id}', filename='{self.filename}', status='{self.status}')>"


class FeatureMeasurementRecord(Base):
    """Stores geospatial feature geometry type, properties, and computed measurements."""

    __tablename__ = "feature_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_index = Column(Integer, nullable=False)
    geometry_type = Column(String(50), nullable=False)
    crs = Column(String(100), nullable=True)
    properties = Column(JSON, nullable=False, default=dict)
    measurement_type = Column(String(20), nullable=True)  # "area", "length", None
    measurement_value = Column(Float, nullable=True)
    measurement_unit = Column(String(20), nullable=True)  # "m²", "m", None
    measurement_status = Column(String(50), nullable=False, default="COMPLETED")  # COMPLETED, UNSUPPORTED, MISSING_CRS, ERROR

    # Relationships
    file = relationship("FileRecord", back_populates="features")

    __table_args__ = (
        Index("idx_file_feature", "file_id", "feature_index"),
    )

    def __repr__(self) -> str:
        return (
            f"<FeatureMeasurementRecord(id={self.id}, file_id='{self.file_id}', "
            f"type='{self.geometry_type}', status='{self.measurement_status}')>"
        )
