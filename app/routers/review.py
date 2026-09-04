"""Verification, audit, and officer review API routes."""

from fastapi import APIRouter, Depends, Header, HTTPException
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
from app.services.portal_service import actor

router = APIRouter(prefix="/claims", tags=["review"])
officer_router = APIRouter(prefix="/officer", tags=["officer"])

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
