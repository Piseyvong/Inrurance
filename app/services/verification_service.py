"""Deterministic claim verification service.

The service compares stored evidence and routes risk to human review. Approval
is allowed only through explicit deterministic rules, never by OCR or an LLM.
"""

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.document import Document
from app.models.extracted_field import ExtractedField
from app.models.ocr_run import OCRRun
from app.models.rule_result import RuleResult
from app.services.policy_service import document_completeness, get_policy
from app.services.processing_log import record_processing_result
from app.services.ocr import confidence_threshold_for_engine

HUMAN_REVIEW_RESULTS = {"mismatch", "missing", "unclear"}


async def run_verification(claim_id: int, db: AsyncSession) -> dict[str, object]:
    """Run deterministic checks and store rule results.

    Returns a report dictionary. Missing evidence, failed OCR, unclear values,
    and mismatches move the claim to `human_review_required`. A clean claim
    under the demo amount threshold can be `auto_approved` by this deterministic
    rules engine, not by AI.
    """

    claim = await db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    policy = await get_policy(db, claim.claim_type)
    document_result = await db.execute(select(Document).where(Document.claim_id == claim_id))
    documents = list(document_result.scalars().all())
    extracted_fields = await _latest_extracted_fields(db, documents)
    latest_ocr_runs = await _latest_ocr_by_document(db, documents)
    from app.services.portal_service import screen_risk
    risk = await screen_risk(claim, db)

    rule_specs = []
    completeness = document_completeness(policy, {document.doc_type for document in documents})
    if completeness["is_complete"]:
        rule_specs.append(("required_documents_present", "match", {"missing": []}))
    else:
        rule_specs.append(("required_documents_present", "missing", {"missing": completeness["missing_document_types"]}))

    for document in documents:
        ocr_run = latest_ocr_runs.get(document.id)
        if ocr_run is None:
            rule_specs.append((f"ocr_available_{document.doc_type}", "missing", {"document_id": document.id}))
        elif ocr_run.status != "succeeded":
            rule_specs.append((f"ocr_available_{document.doc_type}", "unclear", {"document_id": document.id, "status": ocr_run.status}))
        elif ocr_run.average_confidence is None:
            rule_specs.append((f"ocr_confidence_{document.doc_type}", "unclear", {"document_id": document.id, "reason": "confidence_not_available"}))
        elif float(ocr_run.average_confidence) < confidence_threshold_for_engine(ocr_run.engine, float(policy["minimum_ocr_confidence"])):
            rule_specs.append((f"ocr_confidence_{document.doc_type}", "unclear", {
                "document_id": document.id,
                "confidence": float(ocr_run.average_confidence),
                "threshold": confidence_threshold_for_engine(ocr_run.engine, float(policy["minimum_ocr_confidence"])),
                "engine": ocr_run.engine,
            }))
        else:
            rule_specs.append((f"ocr_available_{document.doc_type}", "match", {"document_id": document.id}))

    rule_specs.extend(_required_field_rules(extracted_fields, policy))
    rule_specs.extend(_comparison_rules(extracted_fields, policy))
    rule_specs.extend(_policy_value_rules(claim, extracted_fields, policy))

    reasons = [name for name, result, _details in rule_specs if result in HUMAN_REVIEW_RESULTS]
    if risk["band"] != "low":
        reasons.append("risk_review")
    amount_for_auto_approval = _claim_amount_for_auto_approval(claim, extracted_fields)
    threshold = _decimal_or_none(policy.get("auto_approval_threshold"))
    auto_approved = not reasons and threshold is not None and amount_for_auto_approval is not None and amount_for_auto_approval <= threshold
    if not reasons:
        rule_specs.append(
            (
                "configured_auto_approval_threshold",
                "match" if auto_approved else "not_applicable",
                {
                    "threshold": str(threshold) if threshold is not None else None,
                    "amount": str(amount_for_auto_approval) if amount_for_auto_approval is not None else None,
                    "reason": "clean_claim_under_threshold" if auto_approved else "amount_missing_or_not_under_threshold",
                },
            )
        )
    try:
        # Rule results are the current verification snapshot. Historical runs
        # remain traceable in audit logs without leaking stale issues into the
        # latest decision report.
        await db.execute(delete(RuleResult).where(RuleResult.claim_id == claim.id))
        stored_rules = []
        for name, result, details in rule_specs:
            rule = RuleResult(
                claim_id=claim.id,
                rule_name=name,
                result=result,
                details=json.dumps(details, ensure_ascii=False),
                evaluated_at=datetime.now(timezone.utc),
            )
            db.add(rule)
            stored_rules.append(rule)
        from app.models.domain import Policy
        from app.services.portal_service import triage_outcome
        customer_policy = await db.get(Policy, claim.customer_policy_id) if claim.customer_policy_id else None
        policy_active = customer_policy is None or (
            customer_policy.status == "active"
            and (claim.incident_date is None or customer_policy.start_date <= claim.incident_date <= customer_policy.end_date)
        )
        claim.status = triage_outcome(
            amount=amount_for_auto_approval, threshold=threshold, policy_active=policy_active,
            covered=True, documents_complete=completeness["is_complete"], fields_valid=not reasons,
            risk_band=risk["band"],
        )
        audit_action = "auto_approved" if auto_approved else "verification_completed"
        reasoning = {"decision": claim.status, "policy_type": claim.claim_type, "policy_version": policy["version"], "reasons": sorted(set(reasons)), "compliance_score_pending": True}
        db.add(AuditLog(claim_id=claim.id, actor="rules_engine", action=audit_action, details=json.dumps(reasoning)))
        await db.commit()
        for rule in stored_rules:
            await db.refresh(rule)
        await db.refresh(claim)
        record_processing_result(
            "verification", claim_id=claim.id, outcome=claim.status,
            cause="policy_rules" if not reasons else "missing_or_uncertain_evidence",
            details={"reason_count": len(set(reasons)), "reasons": sorted(set(reasons)), "risk_band": risk["band"]},
        )
        return await build_verification_report(claim_id, db, reasons_override=reasons)
    except Exception:
        await db.rollback()
        raise


async def build_verification_report(
    claim_id: int,
    db: AsyncSession,
    reasons_override: list[str] | None = None,
) -> dict[str, object]:
    """Return the latest verification evidence for a claim."""

    claim = await db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    policy = await get_policy(db, claim.claim_type)
    document_result = await db.execute(
        select(Document).where(Document.claim_id == claim_id).order_by(Document.id.asc())
    )
    documents = list(document_result.scalars().all())
    field_result = await db.execute(
        select(ExtractedField)
        .join(Document, Document.id == ExtractedField.document_id)
        .where(Document.claim_id == claim_id)
        .order_by(ExtractedField.created_at.desc(), ExtractedField.id.desc())
    )
    fields = list(field_result.scalars().all())
    rule_result = await db.execute(
        select(RuleResult)
        .where(RuleResult.claim_id == claim_id)
        .order_by(RuleResult.evaluated_at.desc(), RuleResult.id.desc())
    )
    rules = list(rule_result.scalars().all())
    reasons = reasons_override
    if reasons is None:
        reasons = [rule.rule_name for rule in rules if rule.result in HUMAN_REVIEW_RESULTS]
    latest_ocr_runs = await _latest_ocr_by_document(db, documents)
    return {
        "claim_id": claim.id,
        "claim_status": claim.status,
        "document_completeness": document_completeness(policy, {document.doc_type for document in documents}),
        "documents": documents,
        "extracted_fields": fields,
        "rule_results": rules,
        "reasons_for_human_review": sorted(set(reasons)),
        "evidence_review": _evidence_review_summary(documents, fields, rules, latest_ocr_runs, policy),
        "policy_requirements": policy,
    }


async def list_audit_log(claim_id: int, db: AsyncSession) -> list[AuditLog]:
    """Return audit history for a claim."""

    claim = await db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.claim_id == claim_id)
        .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
    )
    return list(result.scalars().all())


async def record_officer_review(claim_id: int, actor: str, action: str, details: str | None, db: AsyncSession) -> AuditLog:
    """Record a human officer review action as an audit event."""

    claim = await db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    audit = AuditLog(claim_id=claim.id, actor=actor, action=action, details=details)
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    return audit


async def list_officer_claims(db: AsyncSession, status: str | None = "human_review_required") -> list[Claim]:
    """Return claims for the officer portal queue."""

    query = select(Claim)
    if status:
        query = query.where(Claim.status == status)
    result = await db.execute(query.order_by(Claim.created_at.desc(), Claim.id.desc()))
    return list(result.scalars().all())


async def _latest_extracted_fields(db: AsyncSession, documents: list[Document]) -> dict[str, dict[str, ExtractedField]]:
    by_doc_type: dict[str, dict[str, ExtractedField]] = defaultdict(dict)
    for document in documents:
        result = await db.execute(
            select(ExtractedField)
            .where(ExtractedField.document_id == document.id)
            .order_by(ExtractedField.created_at.desc(), ExtractedField.id.desc())
        )
        fields = result.scalars().all()
        for field in fields:
            by_doc_type[document.doc_type].setdefault(field.field_name, field)
    return by_doc_type


async def _latest_ocr_by_document(db: AsyncSession, documents: list[Document]) -> dict[int, OCRRun]:
    runs: dict[int, OCRRun] = {}
    for document in documents:
        result = await db.execute(
            select(OCRRun)
            .where(OCRRun.document_id == document.id)
            .order_by(OCRRun.started_at.desc(), OCRRun.id.desc())
        )
        run = result.scalars().first()
        if run:
            runs[document.id] = run
    return runs


def _required_field_rules(fields: dict[str, dict[str, ExtractedField]], policy: dict) -> list[tuple[str, str, dict[str, object]]]:
    rules = []
    required_by_doc = {item["type"]: item.get("required_fields", []) for item in policy["required_documents"]}
    for doc_type, field_names in required_by_doc.items():
        for field_name in field_names:
            field = fields.get(doc_type, {}).get(field_name)
            if field is None or not field.field_value:
                rules.append((f"required_field_{doc_type}_{field_name}", "missing", {"doc_type": doc_type, "field_name": field_name}))
            elif field.validation_status == "unclear":
                rules.append((f"required_field_{doc_type}_{field_name}", "unclear", {"value": field.field_value}))
            else:
                rules.append((f"required_field_{doc_type}_{field_name}", "match", {"value": field.field_value}))
    policy_number = fields.get("claim_form", {}).get("policy_number")
    if policy_number and policy_number.field_value:
        result = "match" if re.fullmatch(r"[A-Za-z0-9-]{3,50}", policy_number.field_value) else "mismatch"
        rules.append(("policy_number_format", result, {"value": policy_number.field_value}))
    return rules


REQUIRED_FIELDS_BY_DOC = {
    "claim_form": ["claimant_name", "policy_number", "incident_date", "claimed_amount"],
    "medical_report": ["claimant_name", "incident_date", "diagnosis"],
    "receipt": ["total_amount"],
}


def _evidence_review_summary(
    documents: list[Document],
    fields: list[ExtractedField],
    rules: list[RuleResult],
    latest_ocr_runs: dict[int, OCRRun],
    policy: dict,
) -> dict[str, object]:
    """Score extracted evidence without making an approval decision.

    The score is an explainable demo metric: OCR confidence, required-field
    coverage, and deterministic consistency results. It is not a policy
    decision and does not override `claim.status`.
    """

    field_map: dict[int, list[ExtractedField]] = defaultdict(list)
    for field in fields:
        field_map[field.document_id].append(field)

    document_scores = [
        _document_review_score(document, field_map.get(document.id, []), latest_ocr_runs.get(document.id), rules, policy)
        for document in documents
    ]
    scored_rules = [rule for rule in rules if not rule.rule_name.startswith("deterministic_auto_approval")]
    total_checks = len(scored_rules)
    passed_checks = sum(1 for rule in scored_rules if rule.result in {"match", "not_applicable"})
    issue_count = sum(1 for rule in scored_rules if rule.result in HUMAN_REVIEW_RESULTS)
    rule_score = int(round((passed_checks / total_checks) * 100)) if total_checks else 0
    document_score = int(round(sum(item["score"] for item in document_scores) / len(document_scores))) if document_scores else 0
    overall_score = int(round((rule_score * 0.55) + (document_score * 0.45))) if total_checks else document_score
    status = "strong" if overall_score >= 85 and issue_count == 0 else "needs_review" if issue_count else "moderate"
    summary = (
        "Evidence is consistent and complete."
        if status == "strong"
        else "Evidence has missing, unclear, or mismatched items that need review."
        if status == "needs_review"
        else "Evidence is partially complete; review the extracted fields before relying on it."
    )
    return {
        "overall_score": overall_score,
        "status": status,
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "issue_count": issue_count,
        "summary": summary,
        "document_scores": document_scores,
    }


def _document_review_score(
    document: Document,
    fields: list[ExtractedField],
    ocr_run: OCRRun | None,
    rules: list[RuleResult],
    policy: dict,
) -> dict[str, object]:
    requirement = next((item for item in policy["required_documents"] if item["type"] == document.doc_type), {})
    required_fields = requirement.get("required_fields", [])
    valid_required_fields = {
        field.field_name
        for field in fields
        if field.field_name in required_fields and field.field_value and field.validation_status != "unclear"
    }
    required_count = len(required_fields)
    field_score = (len(valid_required_fields) / required_count) * 70 if required_count else 70
    ocr_confidence = float(ocr_run.average_confidence) if ocr_run and ocr_run.average_confidence is not None else None
    ocr_score = (ocr_confidence * 30) if ocr_confidence is not None else (30 if ocr_run and ocr_run.status == "succeeded" else 0)
    related_rules = [rule for rule in rules if document.doc_type in rule.rule_name]
    issue_count = sum(1 for rule in related_rules if rule.result in HUMAN_REVIEW_RESULTS)
    score = max(0, min(100, int(round(field_score + ocr_score - (issue_count * 12)))))
    status = "strong" if score >= 85 and issue_count == 0 else "needs_review" if issue_count else "moderate"
    return {
        "document_id": document.id,
        "doc_type": document.doc_type,
        "score": score,
        "status": status,
        "ocr_confidence": ocr_confidence,
        "extracted_required_fields": len(valid_required_fields),
        "required_fields": required_count,
        "issue_count": issue_count,
    }


def _comparison_rules(fields: dict[str, dict[str, ExtractedField]], policy: dict) -> list[tuple[str, str, dict[str, object]]]:
    comparisons = []
    document_types = [item["type"] for item in policy["required_documents"]]
    for field_name in ("claimant_name", "policy_number", "incident_date", "claim_amount", "currency"):
        refs = [(doc_type, field_name) for doc_type in document_types if fields.get(doc_type, {}).get(field_name) and fields[doc_type][field_name].field_value]
        comparisons.extend((f"consistent_{field_name}_{refs[0][0]}_vs_{ref[0]}", refs[0], ref) for ref in refs[1:])
    rules = []
    for rule_name, left_ref, right_ref in comparisons:
        left = fields.get(left_ref[0], {}).get(left_ref[1])
        right = fields.get(right_ref[0], {}).get(right_ref[1])
        if left is None or not left.field_value or right is None or not right.field_value:
            rules.append((rule_name, "missing", {"left": _value_details(left), "right": _value_details(right)}))
            continue
        result = "match" if _normalise(left.field_value) == _normalise(right.field_value) else "mismatch"
        rules.append((rule_name, result, {"left": _value_details(left), "right": _value_details(right)}))
    return rules


def _claim_amount_for_auto_approval(claim: Claim, fields: dict[str, dict[str, ExtractedField]]) -> Decimal | None:
    """Prefer the receipt total, falling back to the intake amount."""

    extracted_amounts = [doc.get("claim_amount") or doc.get("total_amount") or doc.get("claimed_amount") for doc in fields.values()]
    for value in [*(field.field_value for field in extracted_amounts if field), claim.claimed_amount]:
        parsed = _decimal_or_none(value)
        if parsed is not None:
            return parsed
    return None


def _policy_value_rules(claim: Claim, fields: dict[str, dict[str, ExtractedField]], policy: dict) -> list[tuple[str, str, dict[str, object]]]:
    rules = []
    expected_currency = policy.get("currency")
    max_age_days = policy.get("validation_rules", {}).get("maximum_document_age_days")
    for doc_type, document_fields in fields.items():
        currency = document_fields.get("currency")
        if currency and currency.field_value and policy.get("validation_rules", {}).get("require_currency_match", True):
            result = "match" if currency.field_value.upper() == expected_currency else "mismatch"
            rules.append((f"currency_{doc_type}", result, {"expected": expected_currency, "actual": currency.field_value.upper()}))
        for amount_name in ("claim_amount", "total_amount", "claimed_amount"):
            amount = document_fields.get(amount_name)
            if amount and amount.field_value:
                parsed = _decimal_or_none(amount.field_value)
                rules.append((f"valid_amount_{doc_type}_{amount_name}", "match" if parsed is not None and parsed > 0 else "mismatch", {"value": amount.field_value}))
        for date_name in ("incident_date", "service_date"):
            date_field = document_fields.get(date_name)
            if date_field and date_field.field_value:
                try:
                    parsed_date = date.fromisoformat(date_field.field_value)
                    age = (date.today() - parsed_date).days
                    valid = age >= 0 and (max_age_days is None or age <= int(max_age_days))
                    rules.append((f"valid_date_{doc_type}_{date_name}", "match" if valid else "mismatch", {"value": date_field.field_value, "age_days": age, "maximum_age_days": max_age_days}))
                except ValueError:
                    rules.append((f"valid_date_{doc_type}_{date_name}", "unclear", {"value": date_field.field_value, "reason": "invalid_date_format"}))
        for field_name, expected in (("claimant_name", claim.claimant_name), ("policy_number", claim.policy_number)):
            field = document_fields.get(field_name)
            if expected and field and field.field_value:
                result = "match" if _normalise(field.field_value) == _normalise(str(expected)) else "mismatch"
                rules.append((f"claim_{field_name}_{doc_type}", result, {"claim": str(expected), "document": field.field_value}))
    return rules


def _decimal_or_none(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace("$", "").replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _value_details(field: ExtractedField | None) -> dict[str, object] | None:
    if field is None:
        return None
    return {
        "document_id": field.document_id,
        "field_name": field.field_name,
        "field_value": field.field_value,
        "supporting_line_refs": field.supporting_line_refs,
    }
