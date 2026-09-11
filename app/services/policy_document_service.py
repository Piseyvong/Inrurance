"""Policy-wording storage and constrained retrieval for the demo.

The retrieval index is intentionally transparent: chunks retain their source
policy, version, section, page, and effective date.  It never searches across
products outside the caller's allowed product IDs.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import re
from uuid import uuid4
from zipfile import ZipFile
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.domain import InsuranceProduct, PolicyChunk, PolicyDocument
from app.services.policy_service import get_policy


ALLOWED_POLICY_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def _normalise_text(value: str) -> str:
    return re.sub(r"[ \t]+", " ", value.replace("\r", "")).strip()


def _docx_text(path: Path) -> list[tuple[int, str]]:
    """Extract paragraph text using only the DOCX Open XML package."""

    try:
        with ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except Exception as exc:
        raise HTTPException(422, "The DOCX policy document could not be read.") from exc
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[tuple[int, str]] = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(paragraph.itertext())
        text = _normalise_text(text)
        if text:
            paragraphs.append((1, text))
    return paragraphs


def _pdf_text(path: Path) -> list[tuple[int, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(422, "PDF policy text extraction requires the pypdf package. Install the project requirements and retry.") from exc
    try:
        reader = PdfReader(str(path))
        return [(number, _normalise_text(page.extract_text() or "")) for number, page in enumerate(reader.pages, start=1) if _normalise_text(page.extract_text() or "")]
    except Exception as exc:
        raise HTTPException(422, "The PDF policy document could not be read. Upload a text-based PDF or DOCX file.") from exc


def extract_policy_text(path: Path, suffix: str) -> list[tuple[int, str]]:
    if suffix == ".docx":
        return _docx_text(path)
    if suffix == ".pdf":
        return _pdf_text(path)
    raise HTTPException(415, "Policy documents must be PDF or DOCX files.")


def _heading(text: str) -> bool:
    return bool(re.match(r"^(?:\d+(?:\.\d+)*[.)]?\s+|section\s+|article\s+|part\s+|ផ្នែក)", text, re.I)) or (len(text) < 100 and text.upper() == text and any(char.isalpha() for char in text))


def build_chunks(paragraphs: list[tuple[int, str]], metadata: dict[str, object]) -> list[dict[str, object]]:
    """Create readable chunks while retaining the nearest detected heading."""

    chunks: list[dict[str, object]] = []
    section = "General"
    buffer: list[str] = []
    page_number = 1
    for page, paragraph in paragraphs:
        if _heading(paragraph):
            if buffer:
                chunks.append({"section": section, "page_number": page_number, "content": "\n".join(buffer), "metadata_json": metadata})
                buffer = []
            section = paragraph[:255]
            page_number = page
            continue
        candidate = "\n".join([*buffer, paragraph])
        if len(candidate) > 1300 and buffer:
            chunks.append({"section": section, "page_number": page_number, "content": "\n".join(buffer), "metadata_json": metadata})
            buffer = [paragraph]
            page_number = page
        else:
            buffer.append(paragraph)
    if buffer:
        chunks.append({"section": section, "page_number": page_number, "content": "\n".join(buffer), "metadata_json": metadata})
    return chunks


async def save_policy_document(
    db: AsyncSession, *, product: InsuranceProduct, policy_name: str, policy_code: str, version: str,
    effective_date: date, expiry_date: date | None, language: str, status: str, file: UploadFile, uploaded_by_user_id: int,
) -> PolicyDocument:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(415, "Policy documents must be PDF or DOCX files.")
    mime_type = file.content_type or ("application/pdf" if suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    settings = get_settings()
    destination_dir = settings.upload_dir / "policy_documents"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{uuid4().hex}{suffix}"
    content = await file.read()
    if not content:
        raise HTTPException(422, "The policy document is empty.")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "Policy document exceeds the configured upload limit.")
    destination.write_bytes(content)
    paragraphs = extract_policy_text(destination, suffix)
    if not paragraphs:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, "No readable text was found in the policy document.")
    if status == "active":
        active_versions = list((await db.execute(select(PolicyDocument).where(PolicyDocument.policy_code == policy_code, PolicyDocument.status == "active"))).scalars())
        for prior in active_versions:
            prior.status = "archived"
    claim_type = "medical" if product.product_type == "health" else product.product_type
    policy_configuration = await get_policy(db, claim_type)
    document = PolicyDocument(
        insurance_product_id=product.id, policy_name=policy_name, product_category=product.product_type,
        policy_code=policy_code, version=version, effective_date=effective_date, expiry_date=expiry_date,
        language=language, status=status, original_filename=file.filename or destination.name, mime_type=mime_type,
        file_path=str(destination), extracted_text="\n".join(text for _, text in paragraphs),
        required_documents=policy_configuration["required_documents"],
        configured_rules={"validation_rules": policy_configuration["validation_rules"], "auto_approval_threshold": str(policy_configuration["auto_approval_threshold"]) if policy_configuration["auto_approval_threshold"] is not None else None, "currency": policy_configuration["currency"], "minimum_ocr_confidence": policy_configuration["minimum_ocr_confidence"]},
        uploaded_by_user_id=uploaded_by_user_id,
    )
    db.add(document)
    await db.flush()
    metadata = {"product_type": product.product_type, "policy_id": document.id, "policy_name": policy_name, "policy_version": version, "effective_date": effective_date.isoformat(), "language": language}
    db.add_all(PolicyChunk(policy_document_id=document.id, **chunk) for chunk in build_chunks(paragraphs, metadata))
    await db.commit()
    await db.refresh(document)
    return document


def _terms(question: str) -> set[str]:
    return {item for item in re.findall(r"[A-Za-z0-9]+|[\u1780-\u17ff]{2,}", question.lower()) if len(item) > 1}


async def retrieve_policy_evidence(db: AsyncSession, question: str, product_ids: list[int] | None = None) -> str | None:
    """Return only relevant active policy excerpts, scoped to allowed products."""

    statement = select(PolicyChunk, PolicyDocument).join(PolicyDocument).where(PolicyDocument.status == "active")
    if product_ids is not None:
        if not product_ids:
            return None
        statement = statement.where(PolicyDocument.insurance_product_id.in_(product_ids))
    rows = list((await db.execute(statement)).all())
    terms = _terms(question)
    ranked: list[tuple[int, PolicyChunk, PolicyDocument]] = []
    for chunk, document in rows:
        haystack = f"{chunk.section or ''} {chunk.content}".lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            ranked.append((score, chunk, document))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    excerpts = []
    for _, chunk, document in ranked[:3]:
        excerpts.append(f"Policy: {document.policy_name} | Code: {document.policy_code} | Version: {document.version} | Section: {chunk.section or 'General'} | Page: {chunk.page_number or 'not available'}\nEvidence: {chunk.content}")
    return "\n\n".join(excerpts)
