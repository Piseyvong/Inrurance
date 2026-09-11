from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.document import DocumentRead


class ClaimCreate(BaseModel):
    """Request body for outpatient claim intake."""

    claimant_name: str | None = None
    policy_number: str | None = None
    claim_type: str = "health_outpatient"
    incident_date: date | None = None
    claimed_amount: Decimal | None = None
    customer_policy_id: int | None = None


class ClaimRead(BaseModel):
    """API response for a claim without related documents."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    claimant_name: str | None
    policy_number: str | None
    claim_type: str
    policy_version: int
    incident_date: date | None
    claimed_amount: Decimal | None
    status: str
    created_at: datetime | None


class ClaimWithDocuments(ClaimRead):
    """API response for a claim with document intake status."""

    documents: list[DocumentRead] = Field(default_factory=list)
    document_completeness: dict[str, object]
    missing_required_document_types: list[str] = Field(default_factory=list)
    policy_requirements: dict[str, object]
