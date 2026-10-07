"""Application configuration module using pydantic-settings.

Defines environment-based settings for application operation, upload
limits, database connectivity, and geospatial measurement defaults.
"""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Metadata
    APP_NAME: str = "Geospatial Measurement API"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"
    LOG_LEVEL: str = "INFO"

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./geospatial.db"

    # Storage & Upload Configuration
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".kml", ".zip"]

    # Geospatial Measurement Defaults
    MEASUREMENT_PRECISION: int = 2

    @property
    def max_upload_size_bytes(self) -> int:
        """Return the maximum upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        """Return resolved Path instance for upload directory."""
        path = Path(self.UPLOAD_DIR).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
