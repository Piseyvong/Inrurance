from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.policy import PolicyRead, PolicyWrite
from app.services.policy_service import list_policies, upsert_policy
from app.services.llm_extraction import fields_for_document

router = APIRouter(prefix="/policies", tags=["policy requirements"])


@router.get("", response_model=list[PolicyRead])
async def policies(db: AsyncSession = Depends(get_db)):
    return await list_policies(db)


@router.get("/claim-field-schemas")
async def claim_field_schemas(db: AsyncSession = Depends(get_db)):
    """Return the single source of truth for claim and document fields.

    Clients should fetch this instead of hardcoding different form fields for
    medical, motor, life, accident, property, travel, and future products.
    """

    configured = await list_policies(db)
    claim_fields = ["claim_type", "claimant_name", "policy_number", "incident_date", "claimed_amount"]
    return {
        "claim": {
            "fields": claim_fields,
            "json_example": {
                "claim_type": "medical",
                "claimant_name": "SOK DARA",
                "policy_number": "POL-EXAMPLE-001",
                "incident_date": "2026-09-01",
                "claimed_amount": 57.50,
            },
        },
        "claim_types": [
            {
                "claim_type": policy["claim_type"],
                "display_name": policy["display_name"],
                "documents": [
                    {
                        "doc_type": requirement["type"],
                        "title": requirement["title"],
                        "required_fields": requirement.get("required_fields", []),
                        "semantic_fields": fields_for_document(requirement["type"], requirement.get("required_fields", [])),
                    }
                    for requirement in policy["required_documents"]
                ],
            }
            for policy in configured
        ],
        "extracted_value_format": {
            "field_name": "policy_number",
            "value": "POL-EXAMPLE-001",
            "normalized_value": "POL-EXAMPLE-001",
            "original_ocr_value": "POL-EXAMPLE-001",
            "confidence": 0.98,
            "source_lines": ["page_1_line_4"],
            "source_text": "Policy No: POL-EXAMPLE-001",
            "semantic_reason": "The label identifies this value as the policy number.",
            "validation_status": "VALID",
        },
    }


@router.put("/{claim_type}", response_model=PolicyRead)
async def configure_policy(claim_type: str, payload: PolicyWrite, db: AsyncSession = Depends(get_db)):
    """Admin configuration endpoint; production deployments must protect it by role."""
    payload.claim_type = claim_type
    return await upsert_policy(db, payload)
