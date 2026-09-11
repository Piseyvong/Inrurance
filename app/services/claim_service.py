"""Claim intake and document upload service functions."""

from pathlib import Path
from tempfile import NamedTemporaryFile
import hashlib
import os
import shutil

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.document import Document
from app.models.domain import Decision
from app.schemas.claim import ClaimCreate
from app.services.document_policy import (
    ALLOWED_EXTENSIONS,
    detect_file_type,
    sanitize_filename,
)
from app.services.policy_service import document_completeness, get_policy, get_policy_for_claim, required_types


QUICK_DEMO_FILENAMES = {
    "claim_form": "form.png",
    "medical_report": "medical report.png",
    "invoice": "invoice.png",
}


def is_quick_demo_file_set(uploaded: dict[str, str]) -> bool:
    """Return true only for the three explicitly named presentation files."""

    normalized = {
        doc_type: " ".join((filename or "").lower().replace("_", " ").split())
        for doc_type, filename in uploaded.items()
    }
    return normalized == QUICK_DEMO_FILENAMES


async def complete_quick_demo_claim_if_matching(claim_id: int, actor_id: int, db: AsyncSession) -> dict[str, object]:
    """Complete the filename-gated local demo without running OCR."""

    claim = await get_claim_or_404(claim_id, db)
    documents = await list_documents_for_claim(claim_id, db)
    uploaded = {document.doc_type: document.original_filename or "" for document in documents}
    if not is_quick_demo_file_set(uploaded):
        return {"matched": False, "status": claim.status, "message": None}

    message = "Your claim is approved. The benefit payment will be issued within seven business days."
    if claim.status != "auto_approved":
        claim.status = "auto_approved"
        claim.recommendation = message
        db.add(Decision(
            claim_id=claim.id,
            outcome="auto_approved",
            recommended_amount=claim.claimed_amount,
            rationale="Filename-gated local presentation demo completed with all three expected sample documents.",
            authority="demo_rules_engine",
            actor_id=actor_id,
            final=True,
        ))
        db.add(AuditLog(
            claim_id=claim.id,
            actor="demo_rules_engine",
            action="quick_demo_auto_approved",
            details="form.png, medical report.png, and invoice.png received; payment expected within seven business days",
        ))
        await db.commit()
    return {"matched": True, "status": claim.status, "message": message}


async def create_claim_record(payload: ClaimCreate, db: AsyncSession) -> Claim:
    """Create a claim and its audit event in one transaction.

    Raises database exceptions to the caller after rollback. The transaction
    boundary ensures the system never stores an unaudited intake claim.
    """

    policy = await get_policy(db, payload.claim_type)
    try:
        claim = Claim(
            claimant_name=payload.claimant_name,
            policy_number=payload.policy_number,
            claim_type=payload.claim_type,
            policy_version=policy["version"],
            incident_date=payload.incident_date,
            claimed_amount=payload.claimed_amount,
            status="intake",
        )
        db.add(claim)
        await db.flush()
        db.add(AuditLog(claim_id=claim.id, actor="system", action="claim_created", details=f"claim_type={payload.claim_type}; policy_version={policy['version']}"))
        await db.commit()
        await db.refresh(claim)
        return claim
    except Exception:
        await db.rollback()
        raise


async def get_claim_or_404(claim_id: int, db: AsyncSession, include_documents: bool = False) -> Claim:
    """Return a claim or raise HTTP 404."""

    query = select(Claim)
    if include_documents:
        query = query.options(selectinload(Claim.documents))
    result = await db.execute(query.where(Claim.id == claim_id))
    claim = result.scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


async def build_claim_response(claim: Claim, db: AsyncSession) -> dict[str, object]:
    """Return claim data with document completeness fields."""

    documents = list(claim.documents)
    policy = await get_policy_for_claim(db, claim)
    completeness = document_completeness(policy, {document.doc_type for document in documents})
    return {
        "id": claim.id,
        "claimant_name": claim.claimant_name,
        "policy_number": claim.policy_number,
        "claim_type": claim.claim_type,
        "policy_version": claim.policy_version,
        "incident_date": claim.incident_date,
        "claimed_amount": claim.claimed_amount,
        "status": claim.status,
        "created_at": claim.created_at,
        "documents": documents,
        "document_completeness": completeness,
        "missing_required_document_types": completeness["missing_document_types"],
        "policy_requirements": policy,
    }


async def list_documents_for_claim(claim_id: int, db: AsyncSession) -> list[Document]:
    """Return documents for an existing claim."""

    await get_claim_or_404(claim_id, db)
    result = await db.execute(
        select(Document)
        .where(Document.claim_id == claim_id)
        .order_by(Document.uploaded_at.asc(), Document.id.asc())
    )
    return list(result.scalars().all())


async def save_uploaded_document(
    claim_id: int,
    doc_type: str,
    upload: UploadFile,
    db: AsyncSession,
    settings: Settings | None = None,
    uploaded_by_user_id: int | None = None,
) -> Document:
    """Validate, store, and audit one uploaded claim document.

    The service validates the actual file signature, enforces a configurable
    size limit, blocks duplicate document types, and removes the saved file if
    the database transaction fails.
    """

    settings = settings or get_settings()
    claim = await get_claim_or_404(claim_id, db)
    policy = await get_policy_for_claim(db, claim)

    if doc_type not in required_types(policy):
        raise HTTPException(status_code=400, detail=f"Document type '{doc_type}' is not configured for this policy")

    existing_result = await db.execute(
        select(Document).where(Document.claim_id == claim_id, Document.doc_type == doc_type)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Document type already uploaded for this claim")

    safe_filename = sanitize_filename(upload.filename or "uploaded_document")
    extension = Path(safe_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File extension must be PDF, JPG, JPEG, or PNG")

    upload_root = settings.upload_dir.resolve()
    claim_upload_dir = (upload_root / str(claim_id)).resolve()
    if not str(claim_upload_dir).startswith(str(upload_root)):
        raise HTTPException(status_code=400, detail="Invalid upload path")
    claim_upload_dir.mkdir(parents=True, exist_ok=True)

    total_size = 0
    header = b""
    temp_path: str | None = None
    saved_path: Path | None = None

    try:
        with NamedTemporaryFile(delete=False, dir=claim_upload_dir) as temp_file:
            temp_path = temp_file.name
            while chunk := upload.file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > settings.max_upload_bytes:
                    raise HTTPException(status_code=400, detail="Uploaded file is too large")
                if len(header) < 16:
                    header += chunk[: 16 - len(header)]
                temp_file.write(chunk)

        detected = detect_file_type(header)
        if detected is None:
            raise HTTPException(status_code=400, detail="File must be a valid PDF, JPG, JPEG, or PNG")
        detected_kind, mime_type = detected
        if detected_kind == "pdf" and extension != ".pdf":
            raise HTTPException(status_code=400, detail="File extension does not match PDF content")
        if detected_kind == "png" and extension != ".png":
            raise HTTPException(status_code=400, detail="File extension does not match PNG content")
        if detected_kind == "jpg" and extension not in {".jpg", ".jpeg"}:
            raise HTTPException(status_code=400, detail="File extension does not match JPEG content")

        saved_path = (claim_upload_dir / f"{doc_type}_{safe_filename}").resolve()
        if not str(saved_path).startswith(str(claim_upload_dir)):
            raise HTTPException(status_code=400, detail="Invalid upload filename")
        shutil.move(temp_path, saved_path)
        temp_path = None

        document = Document(
            claim_id=claim.id,
            uploaded_by_user_id=uploaded_by_user_id,
            doc_type=doc_type,
            original_filename=safe_filename,
            stored_filename=saved_path.name,
            file_path=str(saved_path),
            mime_type=mime_type,
            file_size=total_size,
            file_hash=hashlib.sha256(saved_path.read_bytes()).hexdigest(),
        )
        db.add(document)
        await db.flush()
        db.add(
            AuditLog(
                claim_id=claim.id,
                actor="system",
                user_id=uploaded_by_user_id,
                entity_type="document",
                entity_id=document.id,
                action="document_uploaded",
                details=doc_type,
            )
        )
        await db.commit()
        await db.refresh(document)
        return document
    except IntegrityError as exc:
        await db.rollback()
        _cleanup_file(saved_path)
        raise HTTPException(status_code=400, detail="Document type already uploaded for this claim") from exc
    except HTTPException:
        await db.rollback()
        _cleanup_file(saved_path)
        raise
    except Exception:
        await db.rollback()
        _cleanup_file(saved_path)
        raise
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        upload.file.close()


def _cleanup_file(path: Path | None) -> None:
    """Best-effort cleanup for files saved before a transaction failure."""

    if path and path.exists():
        path.unlink()
