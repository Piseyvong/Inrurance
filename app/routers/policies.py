from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.policy import PolicyRead, PolicyWrite
from app.services.policy_service import list_policies, upsert_policy

router = APIRouter(prefix="/policies", tags=["policy requirements"])


@router.get("", response_model=list[PolicyRead])
async def policies(db: AsyncSession = Depends(get_db)):
    return await list_policies(db)


@router.put("/{claim_type}", response_model=PolicyRead)
async def configure_policy(claim_type: str, payload: PolicyWrite, db: AsyncSession = Depends(get_db)):
    """Admin configuration endpoint; production deployments must protect it by role."""
    payload.claim_type = claim_type
    return await upsert_policy(db, payload)
