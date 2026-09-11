import hashlib
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.document import Document
from app.models.extracted_field import ExtractedField
from app.models.domain import ClaimCheck, Decision, InsuranceProduct, Policy, PolicyDocument, PolicyRule, User


def password_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def triage_outcome(*, amount: Decimal | None, threshold: Decimal | None, policy_active: bool,
                   covered: bool, documents_complete: bool, fields_valid: bool, risk_band: str) -> str:
    """Deterministic decision boundary; AI may explain but never override it."""
    if not policy_active or not covered:
        return "coverage_exception"
    if not documents_complete:
        return "waiting_for_documents"
    if risk_band != "low":
        return "risk_review"
    if not fields_valid:
        return "pending_human_review"
    if threshold is not None and amount is not None and amount <= threshold:
        return "auto_approved"
    return "pending_human_review"


async def actor(db: AsyncSession, user_id: int, roles: set[str] | None = None) -> User:
    user = await db.get(User, user_id)
    if not user or not user.active or (roles and user.role not in roles):
        raise HTTPException(403, "Access denied")
    return user


async def seed_demo(db: AsyncSession) -> dict:
    created = False
    users = {}
    for email, full_name, role in [
        ("customer@demo.insure", "Sok Dara", "customer"),
        ("officer@demo.insure", "Dara Claims", "officer"),
        ("admin@demo.insure", "Maly Admin", "admin"),
    ]:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not user:
            user = User(email=email, password_hash=password_hash("demo123"), full_name=full_name, role=role)
            db.add(user); await db.flush(); created = True
        users[role] = user

    product_specs = [
        ("HEALTH-STANDARD", "Health Standard 2026", "health", "Outpatient and hospital benefits with human review safeguards."),
        ("MOTOR-ESSENTIAL", "Motor Essential 2026", "motor", "Private motor accident and damage protection."),
        ("ACCIDENT-PLUS", "Personal Accident Plus 2026", "personal_accident", "Personal accident evidence and benefit review."),
        ("LIFE-SECURE", "Secure Life 2026", "life", "Life protection with officer-reviewed claims."),
    ]
    products = {}
    for code, name, product_type, description in product_specs:
        product = (await db.execute(select(InsuranceProduct).where(InsuranceProduct.code == code, InsuranceProduct.version == 1))).scalar_one_or_none()
        if not product:
            product = InsuranceProduct(code=code, name=name, product_type=product_type, version=1, description=description, effective_from=date(2026, 1, 1))
            db.add(product); await db.flush(); created = True
        products[product_type] = product

    health = products["health"]
    has_health_rules = (await db.execute(select(PolicyRule).where(PolicyRule.insurance_product_id == health.id))).scalars().first()
    if not has_health_rules:
        db.add_all([
            PolicyRule(insurance_product_id=health.id, rule_type="documents", name="Required health documents", configuration={"required":["claim_form","medical_report","invoice"]}, clause_reference="Claims clause 4.1"),
            PolicyRule(insurance_product_id=health.id, rule_type="workflow", name="Automatic approval threshold", configuration={"amount":50,"currency":"USD"}, clause_reference="Workflow rule AP-01"),
            PolicyRule(insurance_product_id=health.id, rule_type="coverage", name="Health claim types", configuration={"covered":["health_outpatient","health_inpatient"]}, clause_reference="Benefits clauses 2.1–2.4"),
        ])
    customer = users["customer"]
    issued = [
        ("HLT-2026-000123", health, Decimal("5000"), Decimal("0")),
        ("ACC-2026-000456", products["personal_accident"], Decimal("25000"), Decimal("0")),
    ]
    for number, product, limit, deductible in issued:
        existing_policy = (await db.execute(select(Policy).where(Policy.policy_number == number))).scalar_one_or_none()
        active_template = (await db.execute(select(PolicyDocument).where(PolicyDocument.insurance_product_id == product.id, PolicyDocument.status == "active").order_by(PolicyDocument.created_at.desc()))).scalars().first()
        if not existing_policy:
            db.add(Policy(policy_number=number, user_id=customer.id, insurance_product_id=product.id, policy_template_id=active_template.id if active_template else None, product_version=product.version, status="active", start_date=date(2026,1,1), end_date=date(2026,12,31), coverage_limit=limit, deductible=deductible, currency="USD")); created = True
        elif active_template and not existing_policy.policy_template_id:
            existing_policy.policy_template_id = active_template.id; created = True
    await db.commit()
    return {"seeded": created, "customer_email": customer.email, "officer_email": users["officer"].email, "admin_email": users["admin"].email, "password": "demo123"}


async def screen_risk(claim: Claim, db: AsyncSession) -> dict:
    docs = list((await db.execute(select(Document).where(Document.claim_id == claim.id))).scalars())
    checks: list[tuple[str, int, str]] = []
    duplicate = 0
    for doc in docs:
        if doc.file_hash:
            match = (await db.execute(select(Document).where(Document.file_hash == doc.file_hash, Document.claim_id != claim.id))).scalars().first()
            if match: duplicate = max(duplicate, 70)
        if doc.reference_number:
            match = (await db.execute(select(Document).where(Document.reference_number == doc.reference_number, Document.claim_id != claim.id))).scalars().first()
            if match: duplicate = max(duplicate, 75)
    invoice_values = list((await db.execute(select(ExtractedField.field_value).join(Document).where(Document.claim_id == claim.id, ExtractedField.field_name == "invoice_number", ExtractedField.field_value.is_not(None)))).scalars())
    for value in invoice_values:
        prior = (await db.execute(select(ExtractedField).join(Document).where(ExtractedField.field_name == "invoice_number", ExtractedField.field_value == value, Document.claim_id != claim.id))).scalars().first()
        if prior: duplicate = max(duplicate, 75)
    checks.append(("duplicate_signal", duplicate, "No duplicate evidence found" if not duplicate else "Matching document hash or reference found"))
    identity = 65 if not claim.policy_number or not claim.claimant_name else 0
    checks.append(("identity_policy_match", identity, "Claim identity fields match the selected policy" if not identity else "Identity or policy field requires verification"))
    integrity = 25 if any(not d.file_hash for d in docs) else 0
    checks.append(("document_integrity", integrity, "Document metadata consistent" if not integrity else "Document fingerprint unavailable"))
    if claim.claim_type.startswith("health"):
        medical = 45 if claim.claimed_amount and claim.claimed_amount > Decimal("5000") else 0
        checks.append(("medical_billing_anomaly", medical, "Amount exceeds demo medical benchmark" if medical else "Amount within configured demo benchmark"))
    score = round(sum(value for _, value, _ in checks) / len(checks))
    band = "low" if score <= 34 else "review" if score <= 59 else "high"
    await db.execute(ClaimCheck.__table__.delete().where(ClaimCheck.claim_id == claim.id, ClaimCheck.category == "risk"))
    for name, value, evidence in checks:
        db.add(ClaimCheck(claim_id=claim.id, category="risk", check_name=name, outcome="flag" if value >= 35 else "pass", score=value, evidence={"summary": evidence}))
    claim.risk_score, claim.risk_band = score, band
    db.add(AuditLog(claim_id=claim.id, actor="risk_engine", action="risk_screen_completed", details=f"band={band}; score={score}"))
    await db.commit()
    return {"score": score, "band": band, "signals":[{"name":n,"score":s,"evidence":e} for n,s,e in checks], "customer_message":"Additional review required." if band != "low" else "Risk screening completed."}
