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
from app.models.domain import ClaimCheck, Decision, InsuranceProduct, Policy, PolicyRule, User


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
    existing = (await db.execute(select(User).where(User.email == "customer@demo.insure"))).scalar_one_or_none()
    if existing:
        return {"seeded": False, "customer_email": existing.email, "password": "demo123"}
    customer = User(email="customer@demo.insure", password_hash=password_hash("demo123"), full_name="Sok Pisey", role="customer")
    officer = User(email="officer@demo.insure", password_hash=password_hash("demo123"), full_name="Dara Claims", role="officer")
    admin = User(email="admin@demo.insure", password_hash=password_hash("demo123"), full_name="Maly Admin", role="admin")
    db.add_all([customer, officer, admin]); await db.flush()
    product = InsuranceProduct(code="HEALTH-STANDARD", name="Health Standard 2026", product_type="health", version=1,
        description="Outpatient and hospital benefits with human review safeguards.", effective_from=date(2026, 1, 1))
    motor = InsuranceProduct(code="MOTOR-ESSENTIAL", name="Motor Essential 2026", product_type="motor", version=1,
        description="Private motor accident and damage protection.", effective_from=date(2026, 1, 1))
    db.add_all([product, motor]); await db.flush()
    db.add_all([
        PolicyRule(insurance_product_id=product.id, rule_type="documents", name="Required health documents", configuration={"required":["claim_form","medical_report","receipt"]}, clause_reference="Claims clause 4.1"),
        PolicyRule(insurance_product_id=product.id, rule_type="workflow", name="Automatic approval threshold", configuration={"amount":50,"currency":"USD"}, clause_reference="Workflow rule AP-01"),
        PolicyRule(insurance_product_id=product.id, rule_type="coverage", name="Health claim types", configuration={"covered":["health_outpatient","health_inpatient"],"waiting_period_days":30}, clause_reference="Benefits clauses 2.1–2.4"),
        PolicyRule(insurance_product_id=product.id, rule_type="benchmark", name="Medical billing benchmarks", configuration={"consultation":25,"lab_test":20,"room_per_day":45}, clause_reference="Schedule of benefits"),
    ])
    db.add(Policy(policy_number="POL-HEALTH-2026-001", user_id=customer.id, insurance_product_id=product.id, product_version=1,
        status="active", start_date=date(2026,1,1), end_date=date(2026,12,31)))
    await db.commit()
    return {"seeded": True, "customer_email": customer.email, "officer_email": officer.email, "admin_email": admin.email, "password": "demo123"}


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
