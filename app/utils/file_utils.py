"""File validation and security utilities for uploads and archive handling."""

import os
import shutil
import zipfile
from pathlib import Path
from typing import List, Optional

from app.core.logging import logger
from app.exceptions.custom_exceptions import (
    InvalidFileException,
    SecurityViolationException,
)

ZIP_MAGIC_SIGNATURES = [
    b"PK\x03\x04",  # Standard zip header
    b"PK\x05\x06",  # Empty zip header
    b"PK\x07\x08",  # Spanned zip header
]


def validate_file_extension(filename: str, allowed_extensions: List[str]) -> str:
    """Validate file extension against allowed whitelist.

    Returns the normalized lowercase extension (e.g. '.kml').
    """
    if not filename or "." not in filename:
        raise InvalidFileException(
            f"Uploaded file has no extension. Allowed formats: {', '.join(allowed_extensions)}"
        )

    ext = Path(filename).suffix.lower()
    allowed_normalized = [e.lower() for e in allowed_extensions]

    if ext not in allowed_normalized:
        raise InvalidFileException(
            f"Unsupported file format '{ext}'. Allowed formats: {', '.join(allowed_extensions)}"
        )
    return ext


def validate_file_content(header: bytes, extension: str) -> None:
    """Validate file content headers (magic bytes) to prevent extension spoofing."""
    if not header or len(header) == 0:
        raise InvalidFileException("The uploaded file is empty (0 bytes).")

    if extension == ".zip":
        if not any(header.startswith(sig) for sig in ZIP_MAGIC_SIGNATURES):
            raise InvalidFileException(
                "Invalid ZIP file: header does not match standard PK zip signatures."
            )

    elif extension == ".kml":
        # KML is XML; verify presence of XML or KML tags in initial bytes
        header_text = header[:1024].decode("utf-8", errors="ignore").strip().lower()
        if not (header_text.startswith("<?xml") or "<kml" in header_text or "<document" in header_text):
            raise InvalidFileException(
                "Invalid KML file: content does not begin with valid XML or <kml> structure."
            )


def inspect_and_validate_zip(zip_path: Path) -> List[str]:
    """Inspect ZIP archive contents for path traversal attempts and valid structure.

    Returns list of normalized file paths inside the archive.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            if not namelist:
                raise InvalidFileException("The uploaded ZIP archive is empty.")

            # Test ZIP integrity
            corrupt_file = zf.testzip()
            if corrupt_file:
                raise InvalidFileException(f"Corrupt entry detected in ZIP archive: {corrupt_file}")

            # Inspect against path traversal attacks (Zip Slip)
            for name in namelist:
                # Disallow absolute paths, parent directory traversals, and Windows volume letters
                if name.startswith("/") or name.startswith("\\"):
                    raise SecurityViolationException(
                        f"Malicious entry detected in ZIP archive (absolute path): {name}"
                    )
                if ".." in name.split("/") or ".." in name.split("\\"):
                    raise SecurityViolationException(
                        f"Malicious entry detected in ZIP archive (path traversal '..'): {name}"
                    )
                if ":" in name:
                    raise SecurityViolationException(
                        f"Malicious entry detected in ZIP archive (volume indicator): {name}"
                    )

            return namelist

    except zipfile.BadZipFile as exc:
        raise InvalidFileException(f"Malformed or invalid ZIP archive: {str(exc)}") from exc


def locate_and_validate_shapefile_components(namelist: List[str]) -> str:
    """Ensure ZIP archive contains mandatory Shapefile components (.shp, .shx, .dbf).

    Returns the archive entry name of the primary .shp file.
    """
    shp_files = [n for n in namelist if n.lower().endswith(".shp")]
    if not shp_files:
        raise InvalidFileException(
            "The uploaded ZIP does not contain a Shapefile (.shp file not found)."
        )

    # Use the first .shp file found (in root or single subfolder)
    primary_shp = shp_files[0]
    base_prefix = primary_shp[:-4]  # Path without .shp

    # Find companion files ignoring case
    shx_found = any(n.lower() == f"{base_prefix.lower()}.shx" for n in namelist)
    dbf_found = any(n.lower() == f"{base_prefix.lower()}.dbf" for n in namelist)

    missing = []
    if not shx_found:
        missing.append(".shx")
    if not dbf_found:
        missing.append(".dbf")

    if missing:
        raise InvalidFileException(
            f"The uploaded ZIP Shapefile is missing required companion file(s): {', '.join(missing)}."
        )

    return primary_shp


def safe_extract_zip(zip_path: Path, extract_dir: Path) -> Path:
    """Extract ZIP archive safely into target directory with traversal boundary checks.

    Returns the absolute Path to the validated .shp file.
    """
    namelist = inspect_and_validate_zip(zip_path)
    primary_shp_rel = locate_and_validate_shapefile_components(namelist)

    extract_dir_resolved = extract_dir.resolve()
    extract_dir_resolved.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # Resolve destination target
            target_path = (extract_dir_resolved / member.filename).resolve()

            # Ensure target stays strictly within extract_dir
            try:
                target_path.relative_to(extract_dir_resolved)
            except ValueError as exc:
                raise SecurityViolationException(
                    f"Path traversal detected during extraction: {member.filename}"
                ) from exc

            # Extract entry
            zf.extract(member, extract_dir_resolved)

    target_shp_path = extract_dir_resolved / primary_shp_rel
    if not target_shp_path.exists():
        raise InvalidFileException(f"Extracted shapefile not found at {primary_shp_rel}")

    return target_shp_path


def cleanup_directory(directory: Optional[Path]) -> None:
    """Safely remove a directory tree and all its contents."""
    if directory and directory.exists() and directory.is_dir():
        try:
            shutil.rmtree(directory, ignore_errors=True)
            logger.debug("Cleaned up temporary directory: %s", directory)
        except Exception as exc:
            logger.warning("Failed to clean up directory %s: %s", directory, exc)
