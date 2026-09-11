"""Officer/admin endpoints for versioned policy wording."""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.domain import InsuranceProduct, PolicyChunk, PolicyDocument
from app.services.policy_document_service import save_policy_document
from app.services.portal_service import actor

router = APIRouter(prefix="/admin/policy-documents", tags=["policy management"])


def serialise(document: PolicyDocument, chunk_count: int = 0) -> dict[str, object]:
    return {"id": document.id, "insurance_product_id": document.insurance_product_id, "policy_name": document.policy_name, "product_category": document.product_category, "policy_code": document.policy_code, "version": document.version, "effective_date": document.effective_date, "expiry_date": document.expiry_date, "language": document.language, "status": document.status, "original_filename": document.original_filename, "chunk_count": chunk_count}


@router.get("")
async def list_policy_documents(x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    await actor(db, x_demo_user, {"officer", "admin"})
    documents = list((await db.execute(select(PolicyDocument).order_by(PolicyDocument.created_at.desc()))).scalars())
    counts = dict((await db.execute(select(PolicyChunk.policy_document_id, func.count(PolicyChunk.id)).group_by(PolicyChunk.policy_document_id))).all())
    return [serialise(document, int(counts.get(document.id, 0))) for document in documents]


@router.post("")
async def upload_policy_document(
    insurance_product_id: int = Form(...), policy_name: str = Form(...), policy_code: str = Form(...), version: str = Form(...),
    effective_date: date = Form(...), expiry_date: date | None = Form(None), language: str = Form("Khmer-English"), status: str = Form("draft"),
    file: UploadFile = File(...), x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db),
):
    user = await actor(db, x_demo_user, {"officer", "admin"})
    if status not in {"draft", "active", "archived"}:
        raise HTTPException(422, "Status must be Draft, Active, or Archived.")
    product = await db.get(InsuranceProduct, insurance_product_id)
    if not product:
        raise HTTPException(404, "Insurance product not found.")
    document = await save_policy_document(db, product=product, policy_name=policy_name.strip(), policy_code=policy_code.strip().upper(), version=version.strip(), effective_date=effective_date, expiry_date=expiry_date, language=language.strip(), status=status, file=file, uploaded_by_user_id=user.id)
    chunk_count = (await db.execute(select(func.count(PolicyChunk.id)).where(PolicyChunk.policy_document_id == document.id))).scalar_one()
    return serialise(document, int(chunk_count))


@router.post("/{document_id}/archive")
async def archive_policy_document(document_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    await actor(db, x_demo_user, {"officer", "admin"})
    document = await db.get(PolicyDocument, document_id)
    if not document:
        raise HTTPException(404, "Policy document not found.")
    document.status = "archived"
    await db.commit()
    return serialise(document)


@router.get("/{document_id}/file")
async def view_policy_document(document_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    await actor(db, x_demo_user, {"officer", "admin"})
    document = await db.get(PolicyDocument, document_id)
    if not document or not Path(document.file_path).is_file():
        raise HTTPException(404, "Policy document file not found.")
    return FileResponse(document.file_path, media_type=document.mime_type, filename=document.original_filename)
