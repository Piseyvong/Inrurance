"""OpenAI-backed chat endpoint for the public platform guide."""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import ConsultationRequestCreate, ConsultationRequestResponse, GuideChatRequest, GuideChatResponse
from app.services.llm_extraction import LLMServiceError, ask_insurance_ai_guide
from app.database import get_db
from app.models.claim import Claim
from app.models.domain import ConsultationRequest, InsuranceProduct, Policy, PolicyRule, User
from app.config import get_settings

router = APIRouter(prefix="/chat", tags=["chat"])


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
        if x_demo_user:
            user = await db.get(User, x_demo_user)
            if user and user.role == "customer":
                mode = "customer"
                policies = list((await db.execute(select(Policy, InsuranceProduct).join(InsuranceProduct).where(Policy.user_id == user.id))).all())
                claims = list((await db.execute(select(Claim).where(Claim.user_id == user.id))).scalars())
                context = f"Customer: {user.full_name}. Policies: " + "; ".join(f"{p.policy_number}, {product.name}, status {p.status}, version {p.product_version}" for p,product in policies)
                context += ". Claims: " + "; ".join(f"#{c.id} {c.claim_type} status {c.status}" for c in claims)
                product_ids = [product.id for _, product in policies]
                rules = list((await db.execute(select(PolicyRule).where(PolicyRule.insurance_product_id.in_(product_ids), PolicyRule.status == "confirmed"))).scalars()) if product_ids else []
                context += ". Confirmed clauses/rules: " + "; ".join(f"{r.name}: {r.configuration} ({r.clause_reference or 'configured rule'})" for r in rules)
        if mode == "guest":
            if any(marker in payload.message.lower() for marker in personal_markers):
                return GuideChatResponse(reply="I can explain the claim process generally, but I need you to sign in before checking a hospital bill, policy, or personal claim. Select Sign in to continue securely.", mode="guest", actions=[{"type":"link","label":"Sign in to continue","href":"/login"}])
            products = list((await db.execute(select(InsuranceProduct).where(InsuranceProduct.active.is_(True)))).scalars())
            settings = get_settings()
            contact = {"company_name": settings.company_name, "phone": settings.consultation_phone, "email": settings.consultation_email, "hours": settings.office_hours, "location": settings.office_location}
            context = "Configured public products: " + "; ".join(f"{p.name} ({p.product_type}): {p.description}" for p in products) + f". Configured company contact: {contact}."
        lower = payload.message.lower()
        if any(term in lower for term in ("consultation", "book", "speak with", "ជួប", "ពិគ្រោះ")):
            actions.append({"type":"consultation","label":"Request a consultation","href":"#consultation"})
        reply = ask_insurance_ai_guide(payload.message, account_context=context, authenticated=mode == "customer")
        if not actions and any(term in reply.lower() for term in ("consultation", "speak with our", "ពិគ្រោះ", "ជួបជាមួយ")):
            actions.append({"type":"consultation","label":"Request a consultation","href":"#consultation"})
        return GuideChatResponse(reply=reply, mode=mode, actions=actions)
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
