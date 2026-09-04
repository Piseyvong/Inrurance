"""Claim-level document pre-check orchestration.

This service ties together the existing OCR, Azure OpenAI extraction, and
deterministic verification steps. The LLM provides structured evidence only;
final routing still belongs to the deterministic verification service.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.extracted_field import ExtractedField
from app.services.claim_service import get_claim_or_404
from app.services.policy_service import document_completeness, get_policy, required_types
from app.services.extraction_service import run_extraction_for_document
from app.services.ocr import OCRProvider, process_document
from app.services.verification_service import run_verification


async def run_claim_precheck(
    claim_id: int,
    db: AsyncSession,
    ocr_provider: OCRProvider | None = None,
) -> dict[str, object]:
    """Run OCR, Azure extraction, and deterministic verification for a claim.

    The claim must already have all required documents. OCR failures are not
    hidden: the failed OCR run remains stored, the claim is routed to human
    review by OCR/verification logic, and extraction is skipped for that file.
    """

    claim = await get_claim_or_404(claim_id, db)
    document_result = await db.execute(
        select(Document)
        .where(Document.claim_id == claim_id)
        .order_by(Document.uploaded_at.asc(), Document.id.asc())
    )
    documents = list(document_result.scalars().all())
    policy = await get_policy(db, claim.claim_type)
    completeness = document_completeness(policy, {document.doc_type for document in documents})
    if not completeness["is_complete"]:
        missing = ", ".join(completeness["missing_document_types"])
        raise HTTPException(status_code=400, detail=f"Upload all required documents before pre-check: {missing}")

    documents_by_type = {document.doc_type: document for document in documents}
    for doc_type in sorted(required_types(policy)):
        document = documents_by_type[doc_type]
        ocr_run = await process_document(document.id, db, provider=ocr_provider)
        if ocr_run.status == "succeeded" and ocr_run.raw_text:
            try:
                await run_extraction_for_document(document.id, db)
            except HTTPException as exc:
                claim.status = "human_review_required"
                db.add(
                    AuditLog(
                        claim_id=claim.id,
                        actor="system",
                        action="extraction_failed",
                        details=f"document_id={document.id}; doc_type={document.doc_type}; status_code={exc.status_code}",
                    )
                )
                await db.commit()

    await _populate_claim_summary_from_extraction(claim, db)
    return await run_verification(claim_id, db)


async def _populate_claim_summary_from_extraction(claim, db: AsyncSession) -> None:
    """Fill intake summary from validated extracted evidence, never user input."""

    result = await db.execute(
        select(ExtractedField, Document.doc_type)
        .join(Document, ExtractedField.document_id == Document.id)
        .where(Document.claim_id == claim.id, ExtractedField.field_value.is_not(None))
        .order_by(ExtractedField.created_at.desc(), ExtractedField.id.desc())
    )
    values: dict[str, list[tuple[str, str]]] = {}
    for field, doc_type in result.all():
        if field.validation_status != "valid" or not field.field_value:
            continue
        values.setdefault(field.field_name, []).append((doc_type, field.field_value.strip()))

    def first(name: str, preferred: tuple[str, ...] = ()) -> str | None:
        candidates = values.get(name, [])
        for doc_type in preferred:
            match = next((value for candidate_type, value in candidates if candidate_type == doc_type), None)
            if match:
                return match
        return candidates[0][1] if candidates else None

    claimant = first("claimant_name", ("claim_form", "medical_report", "invoice"))
    date_value = first("incident_date", ("claim_form",)) or first("service_date", ("medical_report", "invoice"))
    amount_value = first("claim_amount", ("claim_form", "invoice")) or first("total_amount", ("invoice",))
    description = first("incident_description", ("medical_report", "claim_form")) or first("diagnosis", ("medical_report",))
    if claimant:
        claim.claimant_name = claimant
    if description:
        claim.description = description
    if date_value:
        for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                claim.incident_date = datetime.strptime(date_value, pattern).date()
                break
            except ValueError:
                continue
    if amount_value:
        cleaned = amount_value.replace("$", "").replace(",", "").strip()
        try:
            claim.claimed_amount = Decimal(cleaned)
        except InvalidOperation:
            pass
    db.add(AuditLog(claim_id=claim.id, actor="system", action="claim_summary_extracted", details="Claim summary populated from validated document evidence"))
    await db.commit()
