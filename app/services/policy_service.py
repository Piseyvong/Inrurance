"""Structured policy lookup used by intake, OCR, and deterministic review."""

from copy import deepcopy
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import InsurancePolicy
from app.models.domain import Policy, PolicyDocument
from app.schemas.policy import PolicyWrite


def _doc(type_, title, description, fields):
    return {"type": type_, "title": title, "description": description, "required_fields": fields}


DEFAULT_POLICIES = {
    "medical": dict(display_name="Medical claim", description="Treatment, consultation, and pharmacy expenses", required_documents=[_doc("claim_form", "Claim form", "Claimant, policy, and requested amount", ["claimant_name", "policy_number", "incident_date", "claim_amount", "currency"]), _doc("medical_report", "Medical report", "Diagnosis and service evidence", ["patient_name", "treatment_date", "diagnosis"]), _doc("invoice", "Invoice or receipt", "Provider and payment evidence", ["provider_name", "invoice_number", "total_amount", "currency"])], auto_approval_threshold=Decimal("100")),
    "motor": dict(display_name="Motor claim", description="Collision, theft, and vehicle damage", required_documents=[_doc("claim_form", "Claim form", "Claimant and policy details", ["claimant_name", "policy_number", "incident_date", "claim_amount", "currency"]), _doc("incident_report", "Incident or police report", "How and when the incident happened", ["incident_date", "incident_description"]), _doc("repair_estimate", "Repair estimate", "Vendor and repair cost", ["provider_name", "invoice_number", "claim_amount", "currency"]), _doc("damage_photo", "Damage photographs", "Visible evidence of damage", [])], auto_approval_threshold=None),
    "life": dict(display_name="Life claim", description="Death benefit and related cover", required_documents=[_doc("claim_form", "Claim form", "Claimant, beneficiary, and policy details", ["claimant_name", "policy_number", "incident_date"]), _doc("death_certificate", "Death certificate", "Official evidence of death", ["claimant_name", "incident_date"]), _doc("identity_document", "Identity document", "Beneficiary identity evidence", ["claimant_name"])], auto_approval_threshold=None),
    "personal_accident": dict(display_name="Personal accident claim", description="Accident-related medical and incident evidence", required_documents=[_doc("claim_form", "Claim form", "Claimant, policy, and requested amount", ["claimant_name", "policy_number", "incident_date", "claim_amount", "currency"]), _doc("medical_report", "Medical report", "Diagnosis and service evidence", ["patient_name", "treatment_date", "diagnosis"]), _doc("invoice", "Invoice or receipt", "Provider and payment evidence", ["provider_name", "invoice_number", "total_amount", "currency"])], auto_approval_threshold=None),
    "property": dict(display_name="Property claim", description="Home, building, and contents damage", required_documents=[_doc("claim_form", "Claim form", "Claimant, policy, and loss details", ["claimant_name", "policy_number", "incident_date", "claim_amount", "currency"]), _doc("incident_report", "Loss report", "Cause and circumstances of damage", ["incident_date", "incident_description"]), _doc("repair_estimate", "Repair or replacement estimate", "Vendor and expected cost", ["provider_name", "claim_amount", "currency"]), _doc("damage_photo", "Damage photographs", "Visible evidence of the loss", [])], auto_approval_threshold=None),
    "travel": dict(display_name="Travel claim", description="Trip disruption, baggage, and emergency expenses", required_documents=[_doc("claim_form", "Claim form", "Claimant, policy, and loss details", ["claimant_name", "policy_number", "incident_date", "claim_amount", "currency"]), _doc("travel_itinerary", "Travel itinerary", "Booking and travel date evidence", ["claimant_name", "service_date"]), _doc("invoice", "Invoice or receipt", "Expense and vendor evidence", ["provider_name", "invoice_number", "claim_amount", "currency"]), _doc("incident_report", "Incident evidence", "Carrier, police, or provider report", ["incident_date", "incident_description"])], auto_approval_threshold=Decimal("100")),
    "other": dict(display_name="Other insurance claim", description="Claims handled under a configured specialist policy", required_documents=[_doc("claim_form", "Claim form", "Claimant, policy, and loss details", ["claimant_name", "policy_number", "incident_date", "claim_amount", "currency"]), _doc("supporting_evidence", "Supporting evidence", "Evidence required by the applicable policy", ["incident_description"])], auto_approval_threshold=None),
}

for _policy in DEFAULT_POLICIES.values():
    _policy.update(currency="USD", minimum_ocr_confidence=0.80, validation_rules={"maximum_document_age_days": 365, "require_currency_match": True}, active=True, version=1)


LEGACY_REQUIRED_FIELD_ALIASES = {
    "medical_report": {"claimant_name": "patient_name", "service_date": "treatment_date", "incident_description": "diagnosis"},
    "invoice": {"claim_amount": "total_amount"},
    "receipt": {"claim_amount": "total_amount"},
    "repair_estimate": {"invoice_number": "estimate_number", "claim_amount": "total_amount"},
    "death_certificate": {"claimant_name": "deceased_name", "incident_date": "date_of_death"},
    "identity_document": {"claimant_name": "person_name"},
    "travel_itinerary": {"claimant_name": "traveler_name", "service_date": "departure_date"},
    "supporting_evidence": {"incident_description": "description"},
}


def normalize_required_documents(documents: list[dict]) -> list[dict]:
    """Translate legacy universal field names without mutating stored templates."""

    normalized = deepcopy(documents)
    for document in normalized:
        aliases = LEGACY_REQUIRED_FIELD_ALIASES.get(document.get("type"), {})
        document["required_fields"] = list(dict.fromkeys(aliases.get(name, name) for name in document.get("required_fields", [])))
    return normalized


async def get_policy(db: AsyncSession, claim_type: str) -> dict:
    result = await db.execute(select(InsurancePolicy).where(InsurancePolicy.claim_type == claim_type, InsurancePolicy.active.is_(True)))
    stored = result.scalar_one_or_none()
    if stored:
        return {"id": stored.id, "claim_type": stored.claim_type, "display_name": stored.display_name, "description": stored.description, "required_documents": normalize_required_documents(stored.required_documents), "validation_rules": stored.validation_rules or {}, "auto_approval_threshold": stored.auto_approval_threshold, "currency": stored.currency, "minimum_ocr_confidence": stored.minimum_ocr_confidence, "active": stored.active, "version": stored.version}
    policy = DEFAULT_POLICIES.get(claim_type)
    if not policy:
        raise HTTPException(status_code=400, detail=f"No active policy requirements configured for claim type '{claim_type}'")
    resolved = deepcopy(policy)
    resolved["required_documents"] = normalize_required_documents(resolved["required_documents"])
    return {"id": None, "claim_type": claim_type, **resolved}


async def get_policy_for_claim(db: AsyncSession, claim) -> dict:
    """Resolve the immutable template attached to the customer's policy."""

    customer_policy = await db.get(Policy, claim.customer_policy_id) if claim.customer_policy_id else None
    template = await db.get(PolicyDocument, customer_policy.policy_template_id) if customer_policy and customer_policy.policy_template_id else None
    if template and template.required_documents:
        rules = template.configured_rules or {}
        return {
            "id": template.id, "claim_type": claim.claim_type, "display_name": template.policy_name,
            "description": f"Policy document {template.policy_code}, version {template.version}",
            "required_documents": normalize_required_documents(template.required_documents),
            "validation_rules": rules.get("validation_rules", {}),
            "auto_approval_threshold": rules.get("auto_approval_threshold"), "currency": rules.get("currency", customer_policy.currency),
            "minimum_ocr_confidence": rules.get("minimum_ocr_confidence", 0.80), "active": template.status == "active",
            "version": template.version,
        }
    return await get_policy(db, claim.claim_type)


async def list_policies(db: AsyncSession) -> list[dict]:
    stored_result = await db.execute(select(InsurancePolicy).where(InsurancePolicy.active.is_(True)))
    stored_types = {item.claim_type for item in stored_result.scalars().all()}
    claim_types = [*DEFAULT_POLICIES, *(sorted(stored_types - DEFAULT_POLICIES.keys()))]
    return [await get_policy(db, claim_type) for claim_type in claim_types]


async def upsert_policy(db: AsyncSession, payload: PolicyWrite) -> InsurancePolicy:
    result = await db.execute(select(InsurancePolicy).where(InsurancePolicy.claim_type == payload.claim_type))
    policy = result.scalar_one_or_none()
    values = payload.model_dump(mode="json")
    if policy is None:
        policy = InsurancePolicy(**values)
        db.add(policy)
    else:
        for key, value in values.items():
            setattr(policy, key, value)
        policy.version += 1
    await db.commit()
    await db.refresh(policy)
    return policy


def required_types(policy: dict) -> set[str]:
    return {item["type"] for item in policy["required_documents"]}


def document_completeness(policy: dict, existing: set[str]) -> dict:
    missing = sorted(required_types(policy) - existing)
    return {"is_complete": not missing, "missing_document_types": missing}
