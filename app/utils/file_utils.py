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

# Security limits for ZIP archives to prevent decompression bombs and resource exhaustion
MAX_ZIP_ENTRIES = 1000
MAX_ZIP_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MB


def sanitize_filename(filename: str) -> str:
    """Sanitize uploaded filename to prevent directory traversal and metadata attacks.

    Strips directory separators, relative prefixes ('..'), and path characters.
    """
    if not filename:
        return "uploaded_file"
    # Replace backslashes with forward slashes, then take basename
    clean = os.path.basename(filename.replace("\\", "/"))
    # Remove any leading dots or illegal characters
    clean = clean.lstrip(".")
    return clean if clean else "uploaded_file"


def validate_file_extension(filename: str, allowed_extensions: List[str]) -> str:
    """Validate file extension against allowed whitelist.

    Returns the normalized lowercase extension (e.g. '.kml').
    """
    if not filename or "." not in filename:
        raise InvalidFileException(
            f"Uploaded file has no extension. Allowed formats: {', '.join(allowed_extensions)}"
        )

    clean_name = sanitize_filename(filename)
    ext = Path(clean_name).suffix.lower()
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


def is_system_or_metadata_file(name: str) -> bool:
    """Identify operating system metadata files (e.g. macOS __MACOSX, Windows Thumbs.db)."""
    norm = name.replace("\\", "/")
    parts = norm.split("/")
    if any(p.startswith(".") for p in parts if p):
        return True
    if "__MACOSX" in parts:
        return True
    return False


def inspect_and_validate_zip(zip_path: Path) -> List[str]:
    """Inspect ZIP archive contents for path traversal attempts, zip bombs, and valid structure.

    Returns list of normalized file paths inside the archive.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            if not namelist:
                raise InvalidFileException("The uploaded ZIP archive is empty.")

            # Defense against Zip Bomb (excessive entry count)
            if len(namelist) > MAX_ZIP_ENTRIES:
                raise SecurityViolationException(
                    f"ZIP archive contains too many entries ({len(namelist)} > {MAX_ZIP_ENTRIES})."
                )

            # Test ZIP integrity
            corrupt_file = zf.testzip()
            if corrupt_file:
                raise InvalidFileException(f"Corrupt entry detected in ZIP archive: {corrupt_file}")

            total_uncompressed_bytes = 0

            # Inspect against path traversal attacks (Zip Slip) and uncompressed size limits
            for info in zf.infolist():
                name = info.filename
                total_uncompressed_bytes += info.file_size

                if total_uncompressed_bytes > MAX_ZIP_UNCOMPRESSED_BYTES:
                    raise SecurityViolationException(
                        f"ZIP archive exceeds maximum allowable uncompressed size ({MAX_ZIP_UNCOMPRESSED_BYTES // (1024*1024)}MB)."
                    )

                # Disallow absolute paths, parent directory traversals, and Windows volume letters
                if name.startswith("/") or name.startswith("\\"):
                    raise SecurityViolationException(
                        f"Malicious entry detected in ZIP archive (absolute path): {name}"
                    )

                # Check path tokens for traversal
                norm_name = name.replace("\\", "/")
                tokens = [t for t in norm_name.split("/") if t]
                if ".." in tokens:
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
    # Filter out macOS and hidden system files
    clean_entries = [n for n in namelist if not is_system_or_metadata_file(n)]

    shp_files = [n for n in clean_entries if n.lower().endswith(".shp")]
    if not shp_files:
        raise InvalidFileException(
            "The uploaded ZIP does not contain a Shapefile (.shp file not found)."
        )

    # Disallow archives with multiple conflicting shapefile layers
    if len(shp_files) > 1:
        shp_names = [Path(s).name for s in shp_files]
        raise InvalidFileException(
            f"ZIP archive contains multiple Shapefile datasets ({', '.join(shp_names)}). "
            "Please upload an archive with a single Shapefile dataset."
        )

    primary_shp = shp_files[0]
    base_prefix = primary_shp[:-4]  # Path without .shp

    # Find companion files ignoring case
    shx_found = any(n.lower() == f"{base_prefix.lower()}.shx" for n in clean_entries)
    dbf_found = any(n.lower() == f"{base_prefix.lower()}.dbf" for n in clean_entries)

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
            # Skip operating system metadata files
            if is_system_or_metadata_file(member.filename):
                continue

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
