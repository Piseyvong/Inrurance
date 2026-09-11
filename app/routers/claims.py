from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.claim import ClaimCreate, ClaimRead, ClaimWithDocuments
from app.schemas.document import DocumentRead
from app.services.claim_service import (
    build_claim_response,
    complete_quick_demo_claim_if_matching,
    create_claim_record,
    get_claim_or_404,
    list_documents_for_claim,
    save_uploaded_document,
)
from app.models.domain import InsuranceProduct, Policy
from app.models.audit_log import AuditLog
from app.services.portal_service import actor

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", response_model=ClaimRead)
async def create_claim(payload: ClaimCreate, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Create an outpatient claim intake record."""

    user = await actor(db, x_demo_user, {"customer"})
    if payload.customer_policy_id is None:
        raise HTTPException(422, "Select one of your active policies before creating a claim")
    customer_policy = await db.get(Policy, payload.customer_policy_id)
    if not customer_policy or customer_policy.user_id != user.id or customer_policy.status != "active":
        raise HTTPException(403, "The selected active policy does not belong to this customer")
    product = await db.get(InsuranceProduct, customer_policy.insurance_product_id)
    if not product:
        raise HTTPException(404, "Insurance product not found")
    claim = Claim(user_id=user.id, customer_policy_id=customer_policy.id, insurance_product_id=product.id,
        claimant_name=user.full_name, policy_number=customer_policy.policy_number,
        claim_type="medical" if product.product_type == "health" else product.product_type,
        policy_version=customer_policy.product_version, incident_date=payload.incident_date,
        claimed_amount=payload.claimed_amount, currency=customer_policy.currency, status="waiting_for_documents", review_status="not_started")
    db.add(claim); await db.flush(); claim.claim_number=f"CLM-{claim.id:06d}"
    db.add(AuditLog(claim_id=claim.id, actor=user.email, user_id=user.id, actor_role=user.role, action="claim_created", entity_type="claim", entity_id=claim.id))
    await db.commit(); await db.refresh(claim); return claim


@router.post("/{claim_id}/documents", response_model=DocumentRead)
async def upload_document(
    claim_id: int,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    x_demo_user: int = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload one required document for an existing claim."""

    user = await actor(db, x_demo_user)
    claim = await get_claim_or_404(claim_id, db)
    if user.role == "customer" and claim.user_id != user.id:
        raise HTTPException(status_code=404, detail="Claim not found")
    return await save_uploaded_document(claim_id, doc_type, file, db, uploaded_by_user_id=user.id)


@router.post("/{claim_id}/demo-complete")
async def complete_filename_demo(
    claim_id: int,
    x_demo_user: int = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Complete only the explicitly named local presentation sample."""

    user = await actor(db, x_demo_user, {"customer"})
    claim = await get_claim_or_404(claim_id, db)
    if claim.user_id != user.id:
        raise HTTPException(status_code=404, detail="Claim not found")
    return await complete_quick_demo_claim_if_matching(claim_id, user.id, db)


@router.get("/{claim_id}", response_model=ClaimWithDocuments)
async def get_claim(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Return a claim with documents and completeness status."""

    claim = await get_claim_or_404(claim_id, db, include_documents=True)
    user = await actor(db, x_demo_user)
    if user.role == "customer" and claim.user_id != user.id:
        raise HTTPException(status_code=404, detail="Claim not found")
    return await build_claim_response(claim, db)


@router.get("/{claim_id}/documents", response_model=list[DocumentRead])
async def list_claim_documents(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Return uploaded documents for a claim."""

    user = await actor(db, x_demo_user)
    claim = await get_claim_or_404(claim_id, db)
    if user.role == "customer" and claim.user_id != user.id:
        raise HTTPException(status_code=404, detail="Claim not found")
    return await list_documents_for_claim(claim_id, db)
