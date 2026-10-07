"""Custom domain exceptions for the geospatial measurement service."""

from typing import Optional


class GeospatialAPIException(Exception):
    """Base exception for all domain-specific errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = 500,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class InvalidFileException(GeospatialAPIException):
    """Raised when uploaded file fails validation (e.g. extension, empty, missing shapefile components)."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="INVALID_FILE",
            status_code=400,
            details=details,
        )


class FileNotFoundException(GeospatialAPIException):
    """Raised when a requested file or record does not exist."""

    def __init__(self, message: str = "Requested file not found", details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="FILE_NOT_FOUND",
            status_code=404,
            details=details,
        )


class FileTooLargeException(GeospatialAPIException):
    """Raised when an uploaded file exceeds the configured maximum upload size."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="FILE_TOO_LARGE",
            status_code=413,
            details=details,
        )


class CorruptGeospatialFileException(GeospatialAPIException):
    """Raised when a geospatial file cannot be parsed or decoded by GIS drivers."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="CORRUPT_GEOSPATIAL_FILE",
            status_code=422,
            details=details,
        )


class MissingCRSException(GeospatialAPIException):
    """Raised when a dataset lacks Coordinate Reference System definition."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="MISSING_CRS",
            status_code=422,
            details=details,
        )


class InvalidCRSException(GeospatialAPIException):
    """Raised when a dataset has an unparseable or unrecognized CRS."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="INVALID_CRS",
            status_code=422,
            details=details,
        )


class SecurityViolationException(GeospatialAPIException):
    """Raised when a security check fails (e.g. ZIP path traversal attempt)."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="SECURITY_VIOLATION",
            status_code=400,
            details=details,
        )
