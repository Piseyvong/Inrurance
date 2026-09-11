from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.domain import Decision, InsuranceProduct, Policy, PolicyDocument, PolicyRule, User
from app.models.rule_result import RuleResult
from app.services.portal_service import actor, password_hash, screen_risk, seed_demo
from app.services.policy_service import get_policy

router = APIRouter(tags=["portal workflow"])

class LoginBody(BaseModel): email: str; password: str
class StartClaimBody(BaseModel): policy_id: int
class DecisionBody(BaseModel): action: str; reason: str; approved_amount: Decimal | None = None
class ProductBody(BaseModel):
    code: str; name: str; product_type: str; description: str = ""; required_documents: list[str]
    covered_claim_types: list[str]; auto_approval_threshold: Decimal | None = None; active: bool = True
class IssuePolicyBody(BaseModel):
    user_id: int; insurance_product_id: int; policy_template_id: int | None = None; policy_number: str
    start_date: date; end_date: date; coverage_limit: Decimal | None = None; deductible: Decimal | None = None; currency: str = "USD"

@router.post("/demo/seed")
async def demo_seed(db: AsyncSession = Depends(get_db)): return await seed_demo(db)

@router.post("/auth/login")
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == body.email.lower()))).scalar_one_or_none()
    if not user or user.password_hash != password_hash(body.password): raise HTTPException(401, "Invalid email or password")
    return {"user_id":user.id,"full_name":user.full_name,"email":user.email,"role":user.role}

@router.get("/portal/me")
async def portal_me(x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    user = await actor(db, x_demo_user)
    policies = list((await db.execute(select(Policy, InsuranceProduct).join(InsuranceProduct, Policy.insurance_product_id == InsuranceProduct.id).where(Policy.user_id == user.id))).all())
    claims = list((await db.execute(select(Claim).where(Claim.user_id == user.id).order_by(Claim.created_at.desc()))).scalars())
    return {"user":{"id":user.id,"full_name":user.full_name,"email":user.email,"role":user.role},
        "policies":[{"id":p.id,"policy_number":p.policy_number,"status":p.status,"start_date":p.start_date,"end_date":p.end_date,"coverage_limit":p.coverage_limit,"deductible":p.deductible,"currency":p.currency,"product":{"id":pr.id,"name":pr.name,"type":pr.product_type,"version":p.product_version}} for p,pr in policies],
        "claims":[{"id":c.id,"claim_number":c.claim_number or f"CLM-{c.id:06d}","customer_policy_id":c.customer_policy_id,"type":c.claim_type,"amount":c.claimed_amount,"currency":c.currency,"status":c.status,"review_status":c.review_status,"risk_band":c.risk_band,"created_at":c.created_at} for c in claims]}

@router.get("/portal/claims/history")
async def claim_history(page: int = 1, page_size: int = 10, status: str | None = None, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    """Return the signed-in customer's claims, newest first, with pagination.

    The dashboard's inline claims list has no room to show a customer's full
    history once they have more than a handful of claims; this endpoint backs
    a dedicated history page instead.
    """
    user = await actor(db, x_demo_user, {"customer"})
    page = max(page, 1); page_size = min(max(page_size, 1), 50)
    query = select(Claim).where(Claim.user_id == user.id)
    if status: query = query.where(Claim.status == status)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    claims = list((await db.execute(query.order_by(Claim.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars())
    claim_ids = [c.id for c in claims]
    decisions = {d.claim_id: d for d in (await db.execute(select(Decision).where(Decision.claim_id.in_(claim_ids), Decision.final.is_(True)))).scalars()}
    # A verification/precheck run writes rule_results, so its presence marks
    # OCR extraction and compliance checking as done without an extra query
    # per claim to re-derive document completeness from the policy template.
    verified_claim_ids = set((await db.execute(select(RuleResult.claim_id).where(RuleResult.claim_id.in_(claim_ids)).distinct())).scalars().all())
    not_started_statuses = {"waiting_for_documents", "submitted", "intake"}
    return {
        "items": [{
            "id": c.id, "claim_number": c.claim_number or f"CLM-{c.id:06d}", "claim_type": c.claim_type,
            "status": c.status, "review_status": c.review_status,
            "claimed_amount": c.claimed_amount, "currency": c.currency,
            "created_at": c.created_at, "updated_at": c.updated_at,
            "decision": None if c.id not in decisions else {
                "outcome": decisions[c.id].outcome, "amount": decisions[c.id].recommended_amount,
                "rationale": decisions[c.id].rationale, "decided_at": decisions[c.id].created_at,
            },
            "progress": {
                "policy_matched": True,
                "documents_uploaded": c.status not in not_started_statuses,
                "ocr_extracted": c.id in verified_claim_ids,
                "compliance_checked": c.id in verified_claim_ids,
                "decision": c.status == "auto_approved" or c.id in decisions,
            },
        } for c in claims],
        "page": page, "page_size": page_size, "total": total,
        "total_pages": max(1, -(-total // page_size)),
    }

@router.get("/portal/policies/{policy_id}")
async def customer_policy_detail(policy_id:int, x_demo_user:int=Header(...), db:AsyncSession=Depends(get_db)):
    user=await actor(db,x_demo_user,{"customer"}); policy=await db.get(Policy,policy_id)
    if not policy or policy.user_id != user.id: raise HTTPException(404,"Policy not found")
    product=await db.get(InsuranceProduct,policy.insurance_product_id); template=await db.get(PolicyDocument,policy.policy_template_id) if policy.policy_template_id else None
    claim_type="medical" if product.product_type=="health" else product.product_type
    requirements=await get_policy(db,claim_type)
    claims=list((await db.execute(select(Claim).where(Claim.customer_policy_id==policy.id).order_by(Claim.created_at.desc()))).scalars())
    return {"id":policy.id,"policy_number":policy.policy_number,"status":policy.status,"start_date":policy.start_date,"end_date":policy.end_date,"coverage_limit":policy.coverage_limit,"deductible":policy.deductible,"currency":policy.currency,"product":{"id":product.id,"name":product.name,"type":product.product_type,"description":product.description},"template":None if not template else {"id":template.id,"name":template.policy_name,"version":template.version,"document_url":f"/portal/policies/{policy.id}/document"},"required_documents":requirements["required_documents"],"claims":[{"id":c.id,"claim_number":c.claim_number or f"CLM-{c.id:06d}","status":c.status,"created_at":c.created_at} for c in claims]}

@router.get("/portal/policies/{policy_id}/document")
async def customer_policy_document(policy_id:int,x_demo_user:int=Header(...),db:AsyncSession=Depends(get_db)):
    user=await actor(db,x_demo_user,{"customer"}); policy=await db.get(Policy,policy_id)
    if not policy or policy.user_id!=user.id or not policy.policy_template_id: raise HTTPException(404,"Policy document not found")
    template=await db.get(PolicyDocument,policy.policy_template_id)
    if not template or not Path(template.file_path).is_file(): raise HTTPException(404,"Policy document not found")
    return FileResponse(template.file_path,media_type=template.mime_type,filename=template.original_filename)

@router.post("/portal/claims")
async def start_claim(body: StartClaimBody, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    user = await actor(db, x_demo_user, {"customer"}); policy = await db.get(Policy, body.policy_id)
    if not policy or policy.user_id != user.id: raise HTTPException(403, "This policy does not belong to the signed-in customer")
    product = await db.get(InsuranceProduct, policy.insurance_product_id)
    claim = Claim(user_id=user.id, customer_policy_id=policy.id, insurance_product_id=product.id,
        claimant_name=user.full_name, policy_number=policy.policy_number, claim_type="medical" if product.product_type == "health" else product.product_type,
        policy_version=policy.product_version, currency=policy.currency, status="waiting_for_documents", review_status="not_started")
    db.add(claim); await db.flush(); claim.claim_number=f"CLM-{date.today().year}-{claim.id:06d}"; db.add(AuditLog(claim_id=claim.id, actor=user.email,user_id=user.id,actor_role=user.role,action="claim_submitted",entity_type="claim",entity_id=claim.id,details=f"product={product.name}; version={policy.product_version}")); await db.commit(); await db.refresh(claim)
    return {"id":claim.id,"claim_number":claim.claim_number,"status":claim.status,"claim_type":claim.claim_type}

@router.post("/claims/{claim_id}/risk-screen")
async def risk_screen(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    user=await actor(db,x_demo_user); claim=await db.get(Claim,claim_id)
    if not claim or (user.role=="customer" and claim.user_id!=user.id): raise HTTPException(404,"Claim not found")
    return await screen_risk(claim,db)

@router.post("/officer/claims/{claim_id}/decision")
async def officer_decision(claim_id:int, body:DecisionBody, x_demo_user:int=Header(...), db:AsyncSession=Depends(get_db)):
    user=await actor(db,x_demo_user,{"officer","admin"}); claim=await db.get(Claim,claim_id)
    if not claim: raise HTTPException(404,"Claim not found")
    outcomes={"approve":"review_completed","reject":"review_completed","request_documents":"more_information_required","investigate":"under_officer_review","close":"review_completed"}
    if body.action not in outcomes: raise HTTPException(400,"Unsupported officer action")
    claim.status=outcomes[body.action]; claim.review_status=outcomes[body.action]; db.add(Decision(claim_id=claim.id,outcome=claim.status,recommended_amount=body.approved_amount,rationale=body.reason,authority="human",actor_id=user.id,final=body.action in {"approve","reject","close"})); db.add(AuditLog(claim_id=claim.id,actor=user.email,user_id=user.id,actor_role=user.role,action=f"officer_{body.action}",entity_type="claim",entity_id=claim.id,new_value=claim.status,details=body.reason)); await db.commit()
    return {"claim_id":claim.id,"status":claim.status,"authority":"human"}

@router.get("/admin/products")
async def admin_products(x_demo_user:int=Header(...), db:AsyncSession=Depends(get_db)):
    await actor(db,x_demo_user,{"officer","admin"}); products=list((await db.execute(select(InsuranceProduct))).scalars())
    return [{"id":p.id,"code":p.code,"name":p.name,"type":p.product_type,"version":p.version,"active":p.active} for p in products]

@router.get("/admin/customers")
async def admin_customers(x_demo_user:int=Header(...),db:AsyncSession=Depends(get_db)):
    await actor(db,x_demo_user,{"admin"}); customers=list((await db.execute(select(User).where(User.role=="customer",User.active.is_(True)).order_by(User.full_name))).scalars())
    return [{"id":customer.id,"full_name":customer.full_name,"email":customer.email,"phone":customer.phone} for customer in customers]

@router.post("/admin/products")
async def create_product(body:ProductBody, x_demo_user:int=Header(...), db:AsyncSession=Depends(get_db)):
    user=await actor(db,x_demo_user,{"admin"})
    previous=(await db.execute(select(InsuranceProduct).where(InsuranceProduct.code==body.code).order_by(InsuranceProduct.version.desc()))).scalars().first()
    version=(previous.version+1) if previous else 1
    if previous: previous.active=False
    product=InsuranceProduct(code=body.code,name=body.name,product_type=body.product_type,version=version,description=body.description,active=body.active,effective_from=date.today())
    db.add(product);await db.flush()
    db.add_all([
        PolicyRule(insurance_product_id=product.id,rule_type="documents",name="Required documents",configuration={"required":body.required_documents},status="confirmed"),
        PolicyRule(insurance_product_id=product.id,rule_type="coverage",name="Covered claim types",configuration={"covered":body.covered_claim_types},status="confirmed"),
        PolicyRule(insurance_product_id=product.id,rule_type="workflow",name="Automatic approval threshold",configuration={"amount":str(body.auto_approval_threshold) if body.auto_approval_threshold is not None else None,"currency":"USD"},status="confirmed"),
    ]);await db.commit();await db.refresh(product)
    return {"id":product.id,"code":product.code,"name":product.name,"type":product.product_type,"version":product.version,"active":product.active,"configured_by":user.email}

@router.post("/admin/customer-policies")
async def issue_customer_policy(body:IssuePolicyBody,x_demo_user:int=Header(...),db:AsyncSession=Depends(get_db)):
    admin=await actor(db,x_demo_user,{"admin"}); customer=await db.get(User,body.user_id); product=await db.get(InsuranceProduct,body.insurance_product_id)
    template=await db.get(PolicyDocument,body.policy_template_id) if body.policy_template_id else None
    if not customer or customer.role!="customer": raise HTTPException(404,"Customer not found")
    if not product: raise HTTPException(404,"Product not found")
    if template and template.insurance_product_id!=product.id: raise HTTPException(422,"Policy template does not belong to the selected product")
    if body.end_date < body.start_date: raise HTTPException(422,"Policy end date must not precede start date")
    policy=Policy(user_id=customer.id,insurance_product_id=product.id,policy_template_id=template.id if template else None,policy_number=body.policy_number.strip().upper(),product_version=product.version,status="active",start_date=body.start_date,end_date=body.end_date,coverage_limit=body.coverage_limit,deductible=body.deductible,currency=body.currency.upper())
    db.add(policy);await db.commit();await db.refresh(policy)
    return {"id":policy.id,"policy_number":policy.policy_number,"customer":customer.email,"product":product.name,"issued_by":admin.email}
