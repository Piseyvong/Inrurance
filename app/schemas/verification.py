"""Schemas for deterministic verification and officer review APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.document import DocumentRead
from app.schemas.extraction import ExtractedFieldRead


class RuleResultRead(BaseModel):
    """API response for one deterministic verification rule."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    rule_name: str
    result: str
    details: str | None
    evaluated_at: datetime | None


class DocumentReviewScore(BaseModel):
    """Evidence quality score for one uploaded document."""

    document_id: int
    doc_type: str
    score: int
    status: str
    ocr_confidence: float | None
    extracted_required_fields: int
    required_fields: int
    issue_count: int


class EvidenceReviewSummary(BaseModel):
    """Overall evidence score shown as AI-assisted review context."""

    overall_score: int
    status: str
    passed_checks: int
    total_checks: int
    issue_count: int
    summary: str
    document_scores: list[DocumentReviewScore]


class VerificationReport(BaseModel):
    """Full verification report for officer review."""

    claim_id: int
    claim_status: str
    document_completeness: dict[str, object]
    documents: list[DocumentRead]
    extracted_fields: list[ExtractedFieldRead]
    rule_results: list[RuleResultRead]
    reasons_for_human_review: list[str]
    evidence_review: EvidenceReviewSummary
    policy_requirements: dict[str, object]


class AuditLogRead(BaseModel):
    """API response for audit log entries."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    actor: str
    action: str
    details: str | None
    timestamp: datetime | None


class OfficerReviewRequest(BaseModel):
    """Request body for recording an officer review action."""

    actor: str = "claims_officer"
    action: str
    details: str | None = None
