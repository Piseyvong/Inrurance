from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.domain import Decision, InsuranceProduct, Policy, PolicyRule, User
from app.services.portal_service import actor, password_hash, screen_risk, seed_demo

router = APIRouter(tags=["portal workflow"])

class LoginBody(BaseModel): email: str; password: str
class StartClaimBody(BaseModel): policy_id: int
class DecisionBody(BaseModel): action: str; reason: str; approved_amount: Decimal | None = None
class ProductBody(BaseModel):
    code: str; name: str; product_type: str; description: str = ""; required_documents: list[str]
    covered_claim_types: list[str]; auto_approval_threshold: Decimal | None = None; active: bool = True

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
        "policies":[{"id":p.id,"policy_number":p.policy_number,"status":p.status,"start_date":p.start_date,"end_date":p.end_date,"product":{"id":pr.id,"name":pr.name,"type":pr.product_type,"version":p.product_version}} for p,pr in policies],
        "claims":[{"id":c.id,"type":c.claim_type,"amount":c.claimed_amount,"status":c.status,"risk_band":c.risk_band,"created_at":c.created_at} for c in claims]}

@router.post("/portal/claims")
async def start_claim(body: StartClaimBody, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    user = await actor(db, x_demo_user, {"customer"}); policy = await db.get(Policy, body.policy_id)
    if not policy or policy.user_id != user.id: raise HTTPException(403, "This policy does not belong to the signed-in customer")
    product = await db.get(InsuranceProduct, policy.insurance_product_id)
    claim = Claim(user_id=user.id, customer_policy_id=policy.id, insurance_product_id=product.id,
        policy_number=policy.policy_number, claim_type="medical" if product.product_type == "health" else product.product_type,
        policy_version=policy.product_version, status="waiting_for_documents")
    db.add(claim); await db.flush(); db.add(AuditLog(claim_id=claim.id, actor=user.email, action="claim_submitted", details=f"product={product.name}; version={policy.product_version}")); await db.commit(); await db.refresh(claim)
    return {"id":claim.id,"status":claim.status,"claim_type":claim.claim_type}

@router.post("/claims/{claim_id}/risk-screen")
async def risk_screen(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    user=await actor(db,x_demo_user); claim=await db.get(Claim,claim_id)
    if not claim or (user.role=="customer" and claim.user_id!=user.id): raise HTTPException(404,"Claim not found")
    return await screen_risk(claim,db)

@router.post("/officer/claims/{claim_id}/decision")
async def officer_decision(claim_id:int, body:DecisionBody, x_demo_user:int=Header(...), db:AsyncSession=Depends(get_db)):
    user=await actor(db,x_demo_user,{"officer","admin"}); claim=await db.get(Claim,claim_id)
    if not claim: raise HTTPException(404,"Claim not found")
    outcomes={"approve":"approved","reject":"rejected_not_covered","request_documents":"waiting_for_documents","investigate":"risk_review","close":"closed"}
    if body.action not in outcomes: raise HTTPException(400,"Unsupported officer action")
    claim.status=outcomes[body.action]; db.add(Decision(claim_id=claim.id,outcome=claim.status,recommended_amount=body.approved_amount,rationale=body.reason,authority="human",actor_id=user.id,final=body.action in {"approve","reject","close"})); db.add(AuditLog(claim_id=claim.id,actor=user.email,action=f"officer_{body.action}",details=body.reason)); await db.commit()
    return {"claim_id":claim.id,"status":claim.status,"authority":"human"}

@router.get("/admin/products")
async def admin_products(x_demo_user:int=Header(...), db:AsyncSession=Depends(get_db)):
    await actor(db,x_demo_user,{"admin"}); products=list((await db.execute(select(InsuranceProduct))).scalars())
    return [{"id":p.id,"code":p.code,"name":p.name,"type":p.product_type,"version":p.version,"active":p.active} for p in products]

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
