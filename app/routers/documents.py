"""Document processing and extraction API routes."""

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.schemas.extraction import ExtractedFieldRead
from app.schemas.ocr import OCRRunRead
from app.services.extraction_service import run_extraction_for_document
from app.services.ocr import list_ocr_runs, process_document
from app.models.claim import Claim
from app.models.document import Document
from app.models.extracted_field import ExtractedField
from app.models.audit_log import AuditLog
from app.services.portal_service import actor

router = APIRouter(prefix="/documents", tags=["documents"])

class FieldCorrection(BaseModel):
    value: str

async def authorize_document(document_id: int, user_id: int, db: AsyncSession) -> None:
    user = await actor(db, user_id)
    document = await db.get(Document, document_id)
    claim = await db.get(Claim, document.claim_id) if document else None
    if not document or not claim or (user.role == "customer" and claim.user_id != user.id):
        raise HTTPException(404, "Document not found")


@router.post("/{document_id}/process", response_model=OCRRunRead)
async def process_uploaded_document(document_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Run OCR processing for an uploaded document."""

    await authorize_document(document_id, x_demo_user, db)
    return await process_document(document_id, db)


@router.get("/{document_id}/ocr-runs", response_model=list[OCRRunRead])
async def get_document_ocr_runs(document_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Return OCR processing history for a document."""

    await authorize_document(document_id, x_demo_user, db)
    return await list_ocr_runs(document_id, db)


@router.get("/{document_id}/preview")
async def preview_document(document_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Stream an authorised document preview for the claim workspace."""
    await authorize_document(document_id, x_demo_user, db)
    document = await db.get(Document, document_id)
    if document is None or not document.file_path:
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(document.file_path, media_type=document.mime_type or "application/octet-stream", filename=document.original_filename)


@router.post("/{document_id}/extract", response_model=list[ExtractedFieldRead])
async def extract_document_fields(document_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Run structured extraction from the latest successful OCR text."""

    await authorize_document(document_id, x_demo_user, db)
    return await run_extraction_for_document(document_id, db)

@router.patch("/{document_id}/fields/{field_id}", response_model=ExtractedFieldRead)
async def correct_extracted_field(document_id:int, field_id:int, body:FieldCorrection, x_demo_user:int=Header(...), db:AsyncSession=Depends(get_db)):
    await authorize_document(document_id, x_demo_user, db)
    user=await actor(db,x_demo_user); field=await db.get(ExtractedField,field_id); document=await db.get(Document,document_id)
    if not field or field.document_id != document_id: raise HTTPException(404,"Extracted field not found")
    old=field.field_value; field.field_value=body.value.strip(); field.validation_status="corrected"; field.extraction_method="human_correction"
    db.add(AuditLog(claim_id=document.claim_id,actor=user.email,action="field_manually_corrected",details=f"field={field.field_name}; old={old}; new={field.field_value}"));await db.commit();await db.refresh(field);return field
