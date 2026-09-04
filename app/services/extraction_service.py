"""Persistence service for structured extraction results."""

import json

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.extracted_field import ExtractedField
from app.models.ocr_run import OCRRun
from app.services.llm_extraction import LLMServiceError, extract_fields_from_ocr
from app.models.claim import Claim
from app.services.policy_service import get_policy
from app.services.processing_log import record_processing_result


async def run_extraction_for_document(document_id: int, db: AsyncSession) -> list[ExtractedField]:
    """Extract and store fields for the latest successful OCR run.

    The stored values are candidate evidence only. Any unclear or missing value
    remains visible for deterministic verification and officer review.
    """

    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    ocr_result = await db.execute(
        select(OCRRun)
        .where(OCRRun.document_id == document_id, OCRRun.status == "succeeded")
        .order_by(OCRRun.completed_at.desc(), OCRRun.id.desc())
    )
    ocr_run = ocr_result.scalars().first()
    if ocr_run is None or not ocr_run.raw_text:
        raise HTTPException(status_code=400, detail="No successful OCR run is available for extraction")

    claim = await db.get(Claim, document.claim_id)
    policy = await get_policy(db, claim.claim_type)
    requirement = next((item for item in policy["required_documents"] if item["type"] == document.doc_type), None)
    requested_fields = (requirement or {}).get("required_fields", [])
    standard_fields = ["document_type", "claimant_name", "policy_number", "provider_name", "invoice_number", "service_date", "incident_date", "diagnosis", "line_items", "claim_amount", "total_amount", "currency", "incident_description"]
    try:
        extraction = extract_fields_from_ocr(document.doc_type, ocr_run.raw_text, requested_fields=list(dict.fromkeys([*standard_fields, *requested_fields])))
    except LLMServiceError as exc:
        record_processing_result(
            "extraction", claim_id=document.claim_id, document_id=document.id, doc_type=document.doc_type,
            outcome="failed", cause="azure_model", details={"status_code": exc.status_code, "error": exc.public_message},
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc
    except (ValueError, ValidationError) as exc:
        record_processing_result(
            "extraction", claim_id=document.claim_id, document_id=document.id, doc_type=document.doc_type,
            outcome="failed", cause="model_response_format", details={"error": str(exc)[:200] or type(exc).__name__},
        )
        raise HTTPException(status_code=502, detail="Azure OpenAI returned invalid extraction JSON.") from exc
    stored_fields: list[ExtractedField] = []
    try:
        for value in extraction.values:
            field = ExtractedField(
                document_id=document.id,
                ocr_run_id=ocr_run.id,
                field_name=value.field_name,
                field_value=value.field_value,
                confidence=value.confidence,
                supporting_line_refs=json.dumps(value.supporting_line_refs, ensure_ascii=False),
                extraction_method=extraction.method,
                validation_status=value.validation_status,
            )
            db.add(field)
            stored_fields.append(field)
            if value.field_name == "invoice_number" and value.field_value:
                document.reference_number = value.field_value.strip()
        db.add(
            AuditLog(
                claim_id=document.claim_id,
                actor="system",
                action="fields_extracted",
                details=f"document_id={document.id}",
            )
        )
        await db.commit()
        for field in stored_fields:
            await db.refresh(field)
        record_processing_result(
            "extraction", claim_id=document.claim_id, document_id=document.id, doc_type=document.doc_type,
            outcome="succeeded", cause="azure_model", details={"field_count": len(stored_fields), "method": extraction.method},
        )
        return stored_fields
    except Exception:
        await db.rollback()
        raise
