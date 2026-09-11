"""Document preprocessing hooks for OCR.

This demo keeps preprocessing conservative to avoid damaging Khmer diacritics.
The service preserves the original upload and writes derived images under a
separate processed directory when conversion is possible.
"""

from pathlib import Path
import shutil

from app.config import Settings, get_settings


class PreprocessingError(RuntimeError):
    """Raised when a document cannot be prepared for OCR."""


def prepare_for_ocr(file_path: Path, settings: Settings | None = None) -> Path:
    """Prepare a document for OCR and return the first path to process.

    PDF rendering and image enhancement are intentionally light in this MVP.
    If optional tooling is not installed, the original file is returned so the
    OCR provider can report a clear failure instead of hiding the problem.
    """

    return prepare_pages_for_ocr(file_path, settings)[0]


def prepare_pages_for_ocr(
    file_path: Path,
    settings: Settings | None = None,
    require_pdf_images: bool = False,
) -> list[Path]:
    """Prepare a document for OCR and return one image path per page.

    Tesseract expects image inputs, so callers can require PDF rendering to
    succeed. Test and demo providers can still receive the original PDF when
    optional rendering tools are unavailable.
    """

    settings = settings or get_settings()
    source = Path(file_path)
    if not source.exists():
        raise PreprocessingError(f"Document file not found: {source}")

    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    extension = source.suffix.lower()
    if extension in {".jpg", ".jpeg", ".png"}:
        return [_prepare_image(source, settings.processed_dir)]
    if extension == ".pdf":
        return _prepare_pdf_pages(source, settings.processed_dir, require_pdf_images)
    raise PreprocessingError("Unsupported document format for OCR")


def _prepare_image(source: Path, processed_dir: Path) -> Path:
    """Apply conservative image handling when Pillow is available."""

    target = processed_dir / source.name
    try:
        from PIL import Image, ImageOps

        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            image.save(target)
        return target
    except Exception:
        # Keeping the original is safer than applying unverified transforms
        # that could erase small Khmer marks needed for review.
        shutil.copy2(source, target)
        return target


def _prepare_pdf_pages(source: Path, processed_dir: Path, require_images: bool = False) -> list[Path]:
    """Render all PDF pages when Poppler's pdftoppm is available."""

    import subprocess

    output_prefix = processed_dir / source.stem
    for stale_page in processed_dir.glob(f"{source.stem}-*.png"):
        stale_page.unlink(missing_ok=True)
    try:
        subprocess.run(
            ["pdftoppm", "-r", "300", "-png", str(source), str(output_prefix)],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        if require_images:
            raise PreprocessingError(f"PDF rendering failed before OCR: {exc}") from exc
        return [source]

    rendered_pages = sorted(processed_dir.glob(f"{source.stem}-*.png"))
    if rendered_pages:
        return rendered_pages
    if require_images:
        raise PreprocessingError("PDF rendering produced no page images")
    return [source]
