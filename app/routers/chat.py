"""OpenAI-backed chat endpoint for the public platform guide."""

import re

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.schemas.chat import (
    ClaimStatusData,
    ConsultationRequestCreate,
    ConsultationRequestResponse,
    DocumentChecklistItem,
    GuideChatRequest,
    GuideChatResponse,
    PolicyInfoData,
    StructuredData,
)
from app.services.llm_extraction import LLMServiceError, ask_insurance_ai_guide
from app.database import get_db
from app.models.claim import Claim
from app.models.domain import ConsultationRequest, InsuranceProduct, Policy, PolicyRule, User
from app.config import get_settings
from app.services.policy_document_service import retrieve_policy_evidence

router = APIRouter(prefix="/chat", tags=["chat"])

REQUIRED_DOCUMENTS_BY_TYPE = {
    "medical": ["claim_form", "medical_report", "invoice"],
    "health_outpatient": ["claim_form", "medical_report", "invoice"],
    "health_inpatient": ["claim_form", "medical_report", "invoice", "hospital_discharge"],
    "dental": ["claim_form", "dental_report", "invoice"],
    "optical": ["claim_form", "optical_report", "invoice"],
}

DOCUMENT_LABELS = {
    "claim_form": "Claim form",
    "medical_report": "Medical report",
    "invoice": "Invoice / receipt",
    "hospital_discharge": "Hospital discharge summary",
    "dental_report": "Dental report",
    "optical_report": "Optical report",
}

STATUS_LABELS = {
    "approved": "Approved",
    "submitted": "Submitted",
    "pending": "Pending",
    "rejected": "Rejected",
    "human_review_required": "Requires human review",
    "waiting_for_documents": "Waiting for documents",
    "processing": "Processing",
    "active": "Active",
    "inactive": "Inactive",
    "expired": "Expired",
}

NEXT_STEPS_BY_STATUS = {
    "human_review_required": [
        "Submit the required documents listed below so our specialist can complete the review.",
        "Provide any additional context (treatment dates, provider name, uploaded documents).",
        "Reply with 'request contact' if you want our team to contact you.",
    ],
    "waiting_for_documents": [
        "Upload the missing documents listed below.",
        "Once all documents are received, the claim will proceed to review.",
    ],
    "pending": ["Your claim is being processed and will be updated shortly."],
    "submitted": ["Your claim has been received and is awaiting review."],
    "processing": ["Your claim is being processed by our automated checks."],
    "approved": ["Your claim has been approved. Payment details will follow."],
    "rejected": ["Review the reason for rejection and contact our team if you believe this is an error."],
}


def parse_claim_number(message: str) -> int | None:
    """Extract a claim number like 'number 6', '#6', or 'claim 6' from the user message."""
    lower = message.lower()
    patterns = [
        r"(?:number|claim|claim number|claims?)(?:\s*#?|=|:|is)?\s*(\d+)",
        r"#(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return int(match.group(1))
    return None


def build_document_checklist(claim: Claim, required_types: list[str] | None = None) -> list[dict]:
    """Build a checklist of required documents with submission state."""
    types = required_types or REQUIRED_DOCUMENTS_BY_TYPE.get(
        claim.claim_type.replace(" ", "_"), ["claim_form", "medical_report", "invoice"]
    )
    uploaded_types = {doc.doc_type for doc in (claim.documents or [])}
    normalized_uploaded = set()
    for doc_type in uploaded_types:
        normalized_uploaded.add(doc_type)
        normalized_uploaded.add(doc_type.replace("_", " ").replace(" ", "_"))
    checklist = []
    for doc_type in types:
        submitted = doc_type in uploaded_types or doc_type in normalized_uploaded
        checklist.append(
            DocumentChecklistItem(
                name=DOCUMENT_LABELS.get(doc_type, doc_type.replace("_", " ").title()),
                submitted=submitted,
            ).model_dump()
        )
    return checklist


def build_claim_status_data(claim: Claim) -> ClaimStatusData:
    """Convert a Claim row into structured UI data."""
    amount = float(claim.claimed_amount) if claim.claimed_amount is not None else None
    next_steps = NEXT_STEPS_BY_STATUS.get(claim.status)
    return ClaimStatusData(
        id=claim.id,
        claim_type=claim.claim_type,
        status=claim.status,
        amount=amount,
        documents=build_document_checklist(claim),
        next_steps=next_steps,
    )


def build_policy_info_data(policy: Policy, product: InsuranceProduct, premium_products: list[dict]) -> PolicyInfoData:
    """Convert a Policy row into structured UI data."""
    return PolicyInfoData(
        policy_number=policy.policy_number,
        product_name=product.name,
        status=policy.status,
        coverage_type=product.product_type,
        end_date=policy.end_date.isoformat() if policy.end_date else None,
        benefits=premium_products[product.id].get("covered_types") if product.id in premium_products else None,
    )


def get_premium_products_for_products(products: list[InsuranceProduct]) -> dict[int, dict]:
    """Small helper: map product id to descriptive metadata for checklist display."""
    out: dict[int, dict] = {}
    for product in products:
        covered_types = []
        if product.product_type == "health":
            covered_types = ["Health out-patient", "Health in-patient"]
        elif product.product_type == "life":
            covered_types = ["Life protection"]
        elif product.product_type == "travel":
            covered_types = ["Trip coverage", "Emergency medical"]
        out[product.id] = {"covered_types": covered_types}
    return out


@router.post("", response_model=GuideChatResponse)
async def chat_with_guide(payload: GuideChatRequest, x_demo_user: int | None = Header(None), db: AsyncSession = Depends(get_db)) -> GuideChatResponse:
    """Return one OpenAI-generated answer for a public platform question."""

    try:
        mode = "guest"
        actions: list[dict[str, str]] = []
        personal_markers = (
            "my policy", "my policies", "policy do i have", "policies do i have", "my claim", "claim status",
            "can i claim", "hospital bill", "check my", "upload my", "submit my", "my receipt",
            "ខ្ញុំមាន policy", "policy របស់ខ្ញុំ", "claim របស់ខ្ញុំ", "វិក្កយបត្ររបស់ខ្ញុំ", "អាច claim", "ឯកសាររបស់ខ្ញុំ",
        )
        context = None
        policy_product_ids: list[int] | None = None
        structured_data: StructuredData | None = None

        if x_demo_user:
            user = await db.get(User, x_demo_user)
            if user and user.role == "customer":
                mode = "customer"
                policies = list((await db.execute(select(Policy, InsuranceProduct).join(InsuranceProduct).where(Policy.user_id == user.id))).all())
                claims = list((await db.execute(select(Claim).options(selectinload(Claim.documents)).where(Claim.user_id == user.id))).scalars())
                products = [product for _, product in policies]
                premium_products = get_premium_products_for_products(products)
                context = f"Customer: {user.full_name}. Policies: " + "; ".join(f"{p.policy_number}, {product.name}, status {p.status}, version {p.product_version}" for p, product in policies)
                context += ". Claims: " + "; ".join(f"#{c.id} {c.claim_type} status {c.status}" for c in claims)
                product_ids = [product.id for _, product in policies]
                policy_product_ids = product_ids
                rules = list((await db.execute(select(PolicyRule).where(PolicyRule.insurance_product_id.in_(product_ids), PolicyRule.status == "confirmed"))).scalars()) if product_ids else []
                context += ". Confirmed clauses/rules: " + "; ".join(f"{r.name}: {r.configuration} ({r.clause_reference or 'configured rule'})" for r in rules)

                # Build structured data for claim status queries
                lower_message = payload.message.lower()
                claim_number = parse_claim_number(payload.message)
                asking_claim = any(
                    marker in lower_message
                    for marker in ("claim status", "my claim", "claim number", "my claim number", "check claim", "check my claim")
                ) or claim_number

                if asking_claim:
                    target_claims = claims
                    if claim_number:
                        target_claims = [c for c in claims if c.id == claim_number] or [c for c in claims if c.claim_number and str(claim_number) in c.claim_number]
                    if target_claims:
                        structured_claims = [build_claim_status_data(c) for c in target_claims]
                        structured_data = StructuredData(type="claim_status", claims=structured_claims)

                # Build structured data for policy queries
                asking_policy = any(
                    marker in lower_message
                    for marker in ("my policy", "my policies", "policy do i have", "policies do i have", "what policy", "list my")
                )
                if asking_policy and policies:
                    structured_policies = [build_policy_info_data(p, product, premium_products) for p, product in policies]
                    structured_data = StructuredData(type="policy_info", policies=structured_policies)

        if mode == "guest":
            if any(marker in payload.message.lower() for marker in personal_markers):
                return GuideChatResponse(reply="I can explain the claim process generally, but I need you to sign in before checking a hospital bill, policy, or personal claim. Select Sign in to continue securely.", mode="guest", actions=[{"type": "link", "label": "Sign in to continue", "href": "/login"}])
            products = list((await db.execute(select(InsuranceProduct).where(InsuranceProduct.active.is_(True)))).scalars())
            policy_product_ids = [product.id for product in products]
            settings = get_settings()
            contact = {"company_name": settings.company_name, "phone": settings.consultation_phone, "email": settings.consultation_email, "hours": settings.office_hours, "location": settings.office_location}
            context = "Configured public products: " + "; ".join(f"{p.name} ({p.product_type}): {p.description}" for p in products) + f". Configured company contact: {contact}."
        policy_evidence = await retrieve_policy_evidence(db, payload.message, policy_product_ids)
        if policy_evidence:
            context = f"{context or ''}\n\nRetrieved policy evidence (authoritative; cite its policy and section):\n{policy_evidence}"
        lower = payload.message.lower()
        if any(term in lower for term in ("consultation", "book", "speak with", "ជួប", "ពិគ្រោះ")):
            actions.append({"type": "consultation", "label": "Request a consultation", "href": "#consultation"})
        reply = ask_insurance_ai_guide(payload.message, account_context=context, authenticated=mode == "customer")
        if not actions and any(term in reply.lower() for term in ("consultation", "speak with our", "ពិគ្រោះ", "ជួបជាមួយ")):
            actions.append({"type": "consultation", "label": "Request a consultation", "href": "#consultation"})
        return GuideChatResponse(reply=reply, mode=mode, actions=actions, structured_data=structured_data)
    except LLMServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc


@router.post("/consultations", response_model=ConsultationRequestResponse, status_code=201)
async def create_consultation_request(
    payload: ConsultationRequestCreate,
    x_demo_user: int | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> ConsultationRequestResponse:
    """Save a voluntary consultation handoff from either agent mode."""

    if not payload.email and not payload.phone:
        raise HTTPException(status_code=422, detail="Please provide an email address or phone number.")
    user_id = None
    if x_demo_user:
        user = await db.get(User, x_demo_user)
        if user and user.role == "customer":
            user_id = user.id
    request = ConsultationRequest(user_id=user_id, **payload.model_dump())
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return ConsultationRequestResponse(id=request.id, status=request.status, message="Your consultation request has been received. Our team will contact you using the details provided.")