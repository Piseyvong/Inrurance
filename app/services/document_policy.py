"""Document type and upload validation policy.

The constants here define the demo's allowed health insurance intake
documents. Services import this module so routers, verification, and tests use
the same policy instead of duplicating strings.
"""

from pathlib import Path
import re

ALLOWED_DOC_TYPES = {"claim_form", "medical_report", "receipt"}
REQUIRED_DOC_TYPES = {"claim_form", "medical_report", "receipt"}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "png": "image/png",
}


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename without path components.

    The input may come from a browser and must not be trusted. The output is a
    conservative basename that prevents path traversal while preserving enough
    of the original name for officer review.
    """

    basename = Path(filename or "uploaded_document").name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("._")
    return safe or "uploaded_document"


def detect_file_type(header: bytes) -> tuple[str, str] | None:
    """Detect supported file type from magic bytes.

    Returns a `(kind, mime_type)` tuple for PDF, JPG/JPEG, or PNG. The check
    intentionally does not trust filename extension or client-sent MIME type.
    """

    if header.startswith(b"%PDF-"):
        return "pdf", ALLOWED_MIME_TYPES["pdf"]
    if header.startswith(b"\xff\xd8\xff"):
        return "jpg", ALLOWED_MIME_TYPES["jpg"]
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", ALLOWED_MIME_TYPES["png"]
    return None


def document_completeness(existing_doc_types: set[str]) -> dict[str, object]:
    """Return document completeness status for a claim."""

    missing = sorted(REQUIRED_DOC_TYPES - existing_doc_types)
    return {
        "is_complete": not missing,
        "missing_document_types": missing,
    }
