"""OCR provider abstraction and document processing service."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.document import Document
from app.models.ocr_run import OCRRun
from app.services.preprocessing import prepare_pages_for_ocr
from app.services.processing_log import record_processing_result


@dataclass
class OCRLineResult:
    """Recognised text line returned by an OCR provider."""

    line_id: str
    text: str
    page_number: int | None = None
    confidence: float | None = None
    bounding_box: list[float] | None = None


@dataclass
class OCRResult:
    """Normalised OCR provider result persisted in `ocr_runs`."""

    engine: str
    engine_version: str | None
    status: str
    raw_text: str
    lines: list[OCRLineResult] = field(default_factory=list)
    average_confidence: float | None = None
    error_message: str | None = None


class OCRProvider(Protocol):
    """Interface for replaceable OCR engines."""

    engine_name: str

    def extract(self, file_path: Path) -> OCRResult:
        """Extract OCR text from `file_path` and return normalised evidence."""


class KiriOCRProvider:
    """Khmer-English OCR provider using the verified `kiri-ocr` package API."""

    engine_name = "kiri_ocr"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None

    def extract(self, file_path: Path) -> OCRResult:
        """Run Kiri OCR and normalise its line dictionaries."""

        try:
            text, results = self._ocr().extract_text(file_path)
            raw_text = text.strip()
            lines = _normalise_kiri_lines(results)
            average_confidence = _average_confidence(lines)
            return OCRResult(
                engine=self.engine_name,
                engine_version=_kiri_version(),
                status="succeeded" if raw_text else "failed",
                raw_text=raw_text,
                lines=lines,
                average_confidence=average_confidence,
                error_message=None if raw_text else "Kiri OCR produced no text",
            )
        except Exception as exc:
            return OCRResult(
                engine=self.engine_name,
                engine_version=_kiri_version(),
                status="failed",
                raw_text="",
                error_message=str(exc),
            )

    def _ocr(self):
        """Create the Kiri OCR client lazily because model loading is expensive."""

        if self._client is None:
            from kiri_ocr import OCR

            self._client = OCR(decode_method="accurate")
        return self._client


class DemoTextOCRProvider:
    """Synthetic-file OCR provider for local API demos and tests.

    This is not a real OCR engine. It decodes text embedded in synthetic files
    so the full API workflow can be exercised without installing heavy OCR
    dependencies. Real OCR should use Kiri OCR or another verified
    Khmer-English OCR provider.
    """

    engine_name = "demo_text"

    def extract(self, file_path: Path) -> OCRResult:
        raw_text = Path(file_path).read_bytes().decode("utf-8", errors="ignore")
        raw_text = raw_text.replace("%PDF-1.4", "").strip()
        lines = [
            OCRLineResult(line_id=f"line_{index}", text=line, page_number=1, confidence=0.99)
            for index, line in enumerate(raw_text.splitlines(), start=1)
            if line.strip()
        ]
        return OCRResult(
            engine=self.engine_name,
            engine_version="demo",
            status="succeeded" if raw_text else "failed",
            raw_text=raw_text,
            lines=lines,
            average_confidence=0.99 if raw_text else None,
            error_message=None if raw_text else "Synthetic demo file contained no decodable text",
        )


def get_ocr_provider(settings: Settings | None = None) -> OCRProvider:
    """Return the configured OCR provider."""

    settings = settings or get_settings()
    if settings.ocr_provider == "demo_text":
        return DemoTextOCRProvider()
    return KiriOCRProvider(settings)


async def process_document(document_id: int, db: AsyncSession, provider: OCRProvider | None = None) -> OCRRun:
    """Create and complete an OCR run for one document.

    The upload endpoint never runs OCR. This function is isolated so a future
    queue worker can call the same logic without rewriting business rules.
    """

    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    provider = provider or get_ocr_provider()
    ocr_run = OCRRun(document_id=document.id, engine=provider.engine_name, status="processing")
    db.add(ocr_run)
    await db.commit()
    await db.refresh(ocr_run)

    try:
        prepared_paths = prepare_pages_for_ocr(
            Path(document.file_path),
            require_pdf_images=provider.engine_name == "kiri_ocr",
        )
        result = _extract_pages(provider, prepared_paths)
        ocr_run.engine = result.engine
        ocr_run.engine_version = result.engine_version
        ocr_run.status = result.status
        ocr_run.raw_text = result.raw_text
        ocr_run.result_json = json.dumps(
            {"lines": [line.__dict__ for line in result.lines]},
            ensure_ascii=False,
        )
        ocr_run.average_confidence = result.average_confidence
        ocr_run.error_message = result.error_message
        ocr_run.completed_at = datetime.now(timezone.utc)
        action = "ocr_succeeded" if result.status == "succeeded" else "ocr_failed"
        db.add(AuditLog(claim_id=document.claim_id, actor="system", action=action, details=f"document_id={document.id}"))
        await _mark_claim_for_review_when_ocr_is_unclear(document, ocr_run, db)
        await db.commit()
        await db.refresh(ocr_run)
        record_processing_result(
            "ocr", claim_id=document.claim_id, document_id=document.id, doc_type=document.doc_type,
            outcome=ocr_run.status,
            cause="document_quality" if ocr_run.status == "succeeded" and (ocr_run.average_confidence is not None and float(ocr_run.average_confidence) < 0.70) else "ocr_provider",
            details={"engine": ocr_run.engine, "confidence": float(ocr_run.average_confidence) if ocr_run.average_confidence is not None else None, "error": ocr_run.error_message},
        )
        return ocr_run
    except Exception as exc:
        ocr_run.status = "failed"
        ocr_run.error_message = str(exc)
        ocr_run.completed_at = datetime.now(timezone.utc)
        db.add(AuditLog(claim_id=document.claim_id, actor="system", action="ocr_failed", details=f"document_id={document.id}"))
        await _mark_claim_for_review_when_ocr_is_unclear(document, ocr_run, db)
        await db.commit()
        await db.refresh(ocr_run)
        record_processing_result(
            "ocr", claim_id=document.claim_id, document_id=document.id, doc_type=document.doc_type,
            outcome="failed", cause="ocr_provider", details={"engine": ocr_run.engine, "error": str(exc)[:500]},
        )
        return ocr_run


async def list_ocr_runs(document_id: int, db: AsyncSession) -> list[OCRRun]:
    """Return OCR history for a document."""

    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    result = await db.execute(
        select(OCRRun)
        .where(OCRRun.document_id == document_id)
        .order_by(OCRRun.started_at.desc(), OCRRun.id.desc())
    )
    return list(result.scalars().all())


def _extract_pages(provider: OCRProvider, prepared_paths: list[Path]) -> OCRResult:
    """Run OCR for every prepared page and combine normalised evidence."""

    page_results = [provider.extract(path) for path in prepared_paths]
    first_result = page_results[0]
    all_lines: list[OCRLineResult] = []
    raw_text_parts: list[str] = []
    errors: list[str] = []

    for page_number, result in enumerate(page_results, start=1):
        if result.raw_text:
            raw_text_parts.append(result.raw_text)
        if result.error_message:
            errors.append(f"page {page_number}: {result.error_message}")
        for line in result.lines:
            all_lines.append(
                OCRLineResult(
                    line_id=f"page_{page_number}_{line.line_id}",
                    text=line.text,
                    page_number=page_number,
                    confidence=line.confidence,
                    bounding_box=line.bounding_box,
                )
            )

    raw_text = "\n".join(part for part in raw_text_parts if part).strip()
    status = "succeeded" if raw_text and all(result.status == "succeeded" for result in page_results) else "failed"
    return OCRResult(
        engine=first_result.engine,
        engine_version=first_result.engine_version,
        status=status,
        raw_text=raw_text,
        lines=all_lines,
        average_confidence=_average_confidence(all_lines),
        error_message="; ".join(errors) if errors else (None if status == "succeeded" else "OCR produced no text"),
    )


def _normalise_kiri_lines(results: list[dict]) -> list[OCRLineResult]:
    """Convert Kiri result dictionaries into the app's line evidence shape."""

    lines: list[OCRLineResult] = []
    for index, item in enumerate(results, start=1):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        line_number = item.get("line_number") or index
        lines.append(
            OCRLineResult(
                line_id=f"line_{line_number}",
                text=text,
                page_number=1,
                confidence=_as_float(item.get("confidence")),
                bounding_box=_normalise_box(item.get("box") or item.get("bbox") or item.get("bounding_box")),
            )
        )
    return lines


def _average_confidence(lines: list[OCRLineResult]) -> float | None:
    confidences = [line.confidence for line in lines if line.confidence is not None]
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def confidence_threshold_for_engine(engine: str | None, policy_threshold: float = 0.80) -> float:
    """Return the configured threshold used for automated decisions.

    Raw provider scores remain visible in the audit trail. A claim can pass to
    automatic approval only when the configured policy threshold is met.
    """

    return float(policy_threshold)


def _as_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalise_box(value: object) -> list[float] | None:
    if not isinstance(value, list):
        return None
    box = [_as_float(item) for item in value]
    return [item for item in box if item is not None] or None


def _kiri_version() -> str | None:
    try:
        return f"kiri-ocr {version('kiri-ocr')}"
    except PackageNotFoundError:
        return None


async def _mark_claim_for_review_when_ocr_is_unclear(document: Document, ocr_run: OCRRun, db: AsyncSession) -> None:
    """Route OCR risk to human review without approving or rejecting claims."""

    confidence = float(ocr_run.average_confidence) if ocr_run.average_confidence is not None else None
    threshold = confidence_threshold_for_engine(ocr_run.engine, 0.80)
    if ocr_run.status != "succeeded" or not ocr_run.raw_text or (confidence is not None and confidence < threshold):
        claim = await db.get(Claim, document.claim_id)
        if claim is not None:
            claim.status = "human_review_required"
