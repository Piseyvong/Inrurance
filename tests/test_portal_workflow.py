from decimal import Decimal

from app.services.portal_service import triage_outcome
from app.services.claim_service import is_quick_demo_file_set


def decide(**overrides):
    values = dict(amount=Decimal("49.99"), threshold=Decimal("50"), policy_active=True,
                  covered=True, documents_complete=True, fields_valid=True, risk_band="low")
    values.update(overrides)
    return triage_outcome(**values)


def test_clean_claim_under_configured_threshold_is_auto_approved():
    assert decide() == "auto_approved"


def test_missing_document_waits_for_documents():
    assert decide(documents_complete=False) == "waiting_for_documents"


def test_amount_above_threshold_requires_human_review():
    assert decide(amount=Decimal("50.01")) == "pending_human_review"


def test_inactive_policy_is_coverage_exception():
    assert decide(policy_active=False) == "coverage_exception"


def test_duplicate_or_identity_signal_routes_to_risk_review():
    assert decide(risk_band="high") == "risk_review"


def test_quick_demo_requires_the_three_expected_filenames():
    assert is_quick_demo_file_set({
        "claim_form": "form.png",
        "medical_report": "medical_report.png",
        "invoice": "invoice.png",
    })
    assert not is_quick_demo_file_set({
        "claim_form": "other-form.png",
        "medical_report": "medical_report.png",
        "invoice": "invoice.png",
    })
