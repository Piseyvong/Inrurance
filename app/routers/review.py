"""Verification, audit, and officer review API routes."""

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.claim import ClaimRead
from app.schemas.verification import AuditLogRead, OfficerReviewRequest, VerificationReport
from app.services.precheck_service import run_claim_precheck
from app.services.verification_service import (
    build_verification_report,
    list_audit_log,
    list_officer_claims,
    record_officer_review,
    run_verification,
)
from app.models.claim import Claim
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.domain import ClaimCheck, InsuranceProduct, OfficerNote, Policy, PolicyDocument, User
from app.models.ocr_run import OCRRun
from app.models.extracted_field import ExtractedField
from app.models.rule_result import RuleResult
from app.services.portal_service import actor

router = APIRouter(prefix="/claims", tags=["review"])
officer_router = APIRouter(prefix="/officer", tags=["officer"])


class OfficerNoteBody(BaseModel):
    note: str

async def authorize_claim(claim_id: int, user_id: int, db: AsyncSession, officer_only: bool = False):
    user = await actor(db, user_id, {"officer", "admin"} if officer_only else None)
    claim = await db.get(Claim, claim_id)
    if not claim or (user.role == "customer" and claim.user_id != user.id):
        raise HTTPException(404, "Claim not found")


@officer_router.get("/claims", response_model=list[ClaimRead])
async def get_officer_claim_queue(status: str | None = None, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Return claims visible in the officer portal queue."""

    await actor(db, x_demo_user, {"officer", "admin"})
    return await list_officer_claims(db, status)


@officer_router.get("/claims/{claim_id}")
async def get_officer_claim_workspace(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    officer = await actor(db, x_demo_user, {"officer", "admin"})
    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")
    customer = await db.get(User, claim.user_id) if claim.user_id else None
    customer_policy = await db.get(Policy, claim.customer_policy_id) if claim.customer_policy_id else None
    product = await db.get(InsuranceProduct, claim.insurance_product_id) if claim.insurance_product_id else None
    template = await db.get(PolicyDocument, customer_policy.policy_template_id) if customer_policy and customer_policy.policy_template_id else None
    documents = list((await db.execute(select(Document).where(Document.claim_id == claim.id).order_by(Document.uploaded_at))).scalars())
    review_documents = []
    for document in documents:
        ocr = (await db.execute(select(OCRRun).where(OCRRun.document_id == document.id).order_by(OCRRun.started_at.desc(), OCRRun.id.desc()))).scalars().first()
        field_query = select(ExtractedField).where(ExtractedField.document_id == document.id)
        if ocr:
            field_query = field_query.where(ExtractedField.ocr_run_id == ocr.id)
        fields = list((await db.execute(field_query.order_by(ExtractedField.created_at.desc(), ExtractedField.id.desc()))).scalars())
        rules = list((await db.execute(select(RuleResult).where(RuleResult.claim_id == claim.id, RuleResult.rule_name.contains(document.doc_type)))).scalars())
        review_documents.append({
            "id": document.id, "doc_type": document.doc_type, "original_filename": document.original_filename,
            "mime_type": document.mime_type, "file_size": document.file_size, "uploaded_at": document.uploaded_at,
            "ocr_status": document.ocr_status, "extraction_status": document.extraction_status, "verification_status": document.verification_status,
            "view_url": f"/officer/claims/{claim.id}/documents/{document.id}/view", "download_url": f"/officer/claims/{claim.id}/documents/{document.id}/download",
            "ocr": None if not ocr else {"id": ocr.id, "status": ocr.status, "engine": ocr.engine, "engine_version": ocr.engine_version, "language": ocr.language, "confidence": float(ocr.average_confidence) if ocr.average_confidence is not None else None, "raw_text": ocr.raw_text, "cleaned_text": ocr.cleaned_text or ocr.raw_text, "processed_at": ocr.completed_at, "error": ocr.error_message},
            "fields": [{"id": field.id, "field_name": field.field_name, "extracted_value": field.field_value, "normalized_value": field.normalized_value, "original_ocr_value": field.original_ocr_value, "effective_value": field.officer_corrected_value or field.normalized_value or field.field_value, "corrected_value": field.officer_corrected_value, "confidence": float(field.confidence) if field.confidence is not None else None, "supporting_line_refs": field.supporting_line_refs, "source_text": field.source_text, "semantic_reason": field.semantic_reason, "validation_status": field.validation_status} for field in fields],
            "verification": [{"name": rule.rule_name, "result": rule.result, "details": rule.details} for rule in rules],
        })
    notes = list((await db.execute(select(OfficerNote, User).join(User, OfficerNote.officer_user_id == User.id).where(OfficerNote.claim_id == claim.id).order_by(OfficerNote.created_at.desc()))).all())
    checks = list((await db.execute(select(ClaimCheck).where(ClaimCheck.claim_id == claim.id))).scalars())
    db.add(AuditLog(claim_id=claim.id, actor=officer.email, user_id=officer.id, actor_role=officer.role, action="officer_opened_claim", entity_type="claim", entity_id=claim.id))
    await db.commit()
    return {
        "claim": {"id": claim.id, "claim_number": claim.claim_number or f"CLM-{claim.id:06d}", "claim_type": claim.claim_type, "incident_date": claim.incident_date, "description": claim.description, "requested_amount": claim.claimed_amount, "currency": claim.currency, "workflow_status": claim.status, "review_status": claim.review_status, "created_at": claim.created_at},
        "customer": None if not customer else {"id": customer.id, "full_name": customer.full_name, "email": customer.email, "phone": customer.phone},
        "policy": None if not customer_policy else {"id": customer_policy.id, "policy_number": customer_policy.policy_number, "status": customer_policy.status, "start_date": customer_policy.start_date, "end_date": customer_policy.end_date, "coverage_limit": customer_policy.coverage_limit, "deductible": customer_policy.deductible, "currency": customer_policy.currency},
        "product": None if not product else {"id": product.id, "code": product.code, "name": product.name, "category": product.product_type, "version": product.version},
        "policy_template": None if not template else {"id": template.id, "name": template.policy_name, "version": template.version},
        "documents": review_documents,
        "risk": {"score": claim.risk_score, "band": claim.risk_band, "checks": [{"name": check.check_name, "outcome": check.outcome, "score": check.score, "evidence": check.evidence} for check in checks]},
        "notes": [{"id": note.id, "note": note.note, "officer": user.full_name, "created_at": note.created_at} for note, user in notes],
    }


async def _officer_document(claim_id: int, document_id: int, user_id: int, db: AsyncSession) -> Document:
    await actor(db, user_id, {"officer", "admin"})
    document = await db.get(Document, document_id)
    if not document or document.claim_id != claim_id or not Path(document.file_path).is_file():
        raise HTTPException(404, "Document not found")
    return document


@officer_router.get("/claims/{claim_id}/documents")
async def get_officer_documents(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    await authorize_claim(claim_id, x_demo_user, db, officer_only=True)
    documents = list((await db.execute(select(Document).where(Document.claim_id == claim_id))).scalars())
    return [{"id": item.id, "doc_type": item.doc_type, "original_filename": item.original_filename, "mime_type": item.mime_type, "file_size": item.file_size, "uploaded_at": item.uploaded_at, "ocr_status": item.ocr_status, "extraction_status": item.extraction_status, "verification_status": item.verification_status} for item in documents]


@officer_router.get("/claims/{claim_id}/documents/{document_id}")
async def get_officer_document_detail(claim_id: int, document_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    document = await _officer_document(claim_id, document_id, x_demo_user, db)
    return {"id": document.id, "claim_id": document.claim_id, "doc_type": document.doc_type, "original_filename": document.original_filename, "mime_type": document.mime_type, "file_size": document.file_size, "uploaded_at": document.uploaded_at, "ocr_status": document.ocr_status, "extraction_status": document.extraction_status, "verification_status": document.verification_status}


@officer_router.get("/claims/{claim_id}/documents/{document_id}/view")
async def view_officer_document(claim_id: int, document_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    document = await _officer_document(claim_id, document_id, x_demo_user, db)
    return FileResponse(document.file_path, media_type=document.mime_type or "application/octet-stream")


@officer_router.get("/claims/{claim_id}/documents/{document_id}/download")
async def download_officer_document(claim_id: int, document_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    document = await _officer_document(claim_id, document_id, x_demo_user, db)
    return FileResponse(document.file_path, media_type="application/octet-stream", filename=document.original_filename)


@officer_router.post("/claims/{claim_id}/notes")
async def add_officer_note(claim_id: int, body: OfficerNoteBody, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    officer = await actor(db, x_demo_user, {"officer", "admin"})
    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")
    if not body.note.strip():
        raise HTTPException(422, "Note cannot be empty")
    note = OfficerNote(claim_id=claim.id, officer_user_id=officer.id, note=body.note.strip())
    db.add(note); await db.flush()
    db.add(AuditLog(claim_id=claim.id, actor=officer.email, user_id=officer.id, actor_role=officer.role, action="officer_added_note", entity_type="officer_note", entity_id=note.id, new_value=note.note))
    await db.commit(); await db.refresh(note)
    return {"id": note.id, "note": note.note, "officer": officer.full_name, "created_at": note.created_at}


@router.post("/{claim_id}/verification", response_model=VerificationReport)
async def verify_claim(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Run deterministic verification for a claim."""

    await authorize_claim(claim_id, x_demo_user, db)
    return await run_verification(claim_id, db)


@router.post("/{claim_id}/precheck", response_model=VerificationReport)
async def precheck_claim_documents(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Run OCR, Azure extraction, then deterministic verification."""

    await authorize_claim(claim_id, x_demo_user, db)
    return await run_claim_precheck(claim_id, db)


@router.get("/{claim_id}/verification", response_model=VerificationReport)
async def get_claim_verification(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Return the latest verification report for a claim."""

    await authorize_claim(claim_id, x_demo_user, db)
    return await build_verification_report(claim_id, db)


@router.get("/{claim_id}/audit", response_model=list[AuditLogRead])
async def get_claim_audit(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Return audit history for a claim."""

    await authorize_claim(claim_id, x_demo_user, db)
    return await list_audit_log(claim_id, db)


@router.post("/{claim_id}/review", response_model=AuditLogRead)
async def record_review_action(
    claim_id: int,
    payload: OfficerReviewRequest,
    x_demo_user: int = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Record a human officer review action."""

    await authorize_claim(claim_id, x_demo_user, db, officer_only=True)
    return await record_officer_review(claim_id, payload.actor, payload.action, payload.details, db)
