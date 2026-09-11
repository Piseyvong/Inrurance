"""Semantic extraction boundaries that prevent cross-concept field mapping."""

import json

from app.config import Settings
from app.models.extracted_field import ExtractedField
from app.schemas.extraction import ExtractedValue
from app.services import llm_extraction
from app.services.llm_extraction import fields_for_document, validate_semantic_extraction
from app.services.verification_service import _chronology_rules


def test_document_schemas_keep_insurance_concepts_separate():
    invoice = set(fields_for_document("invoice"))
    assert {"invoice_date", "service_date", "total_amount", "line_items"} <= invoice
    assert "incident_date" not in invoice
    assert {"reported_incident_date", "claim_amount", "diagnosis"} <= invoice

    report = set(fields_for_document("medical_report"))
    assert {"medical_report_number", "consultation_date", "treatment_date", "diagnosis", "procedures"} <= report
    assert {"invoice_number", "invoice_date", "total_amount"}.isdisjoint(report)

    claim_form = set(fields_for_document("claim_form"))
    assert {"incident_date", "treatment_date", "claim_amount"} <= claim_form


def test_untrusted_model_fields_are_filtered_and_traceability_is_required():
    evidence = {"page_1_line_1": "Invoice Date: 12 Apr 2025", "page_1_line_2": "X-Ray (Chest)"}
    values = [
        ExtractedValue(field_name="invoice_date", value="12 Apr 2025", normalized_value="2025-04-12", confidence=0.98, source_lines=["page_1_line_1"], source_text=evidence["page_1_line_1"], semantic_reason="Invoice issue date", validation_status="valid"),
        ExtractedValue(field_name="incident_date", value="12 Apr 2025", normalized_value="2025-04-12", confidence=0.90, source_lines=["page_1_line_1"], source_text=evidence["page_1_line_1"], semantic_reason="Wrongly reused date", validation_status="VALID"),
        ExtractedValue(field_name="diagnosis", value="X-Ray (Chest)", confidence=0.60, source_lines=["page_1_line_2"], source_text=evidence["page_1_line_2"], semantic_reason="Wrongly treated procedure as diagnosis", validation_status="VALID"),
        ExtractedValue(field_name="line_items", value="X-Ray (Chest)", normalized_value="X-Ray (Chest)", confidence=0.94, source_lines=["page_1_line_2"], source_text=evidence["page_1_line_2"], semantic_reason="A billed procedure line", validation_status="VALID"),
        ExtractedValue(field_name="total_amount", value="124.95", normalized_value="124.95", confidence=0.9, source_lines=["made_up_line"], source_text="Total payable: $124.95", semantic_reason="Bill total", validation_status="VALID"),
    ]

    result = validate_semantic_extraction(values, fields_for_document("invoice"), evidence, [])
    by_name = {item.field_name: item for item in result}
    assert set(by_name) == {"invoice_date", "line_items", "total_amount"}
    assert by_name["invoice_date"].validation_status == "VALID"
    assert by_name["total_amount"].validation_status == "UNCLEAR"


def test_claim_form_preserves_incident_and_treatment_as_separate_dates():
    evidence = {
        "page_1_line_1": "Motorcycle accident occurred on 10 August 2026.",
        "page_1_line_2": "Patient received hospital treatment on 12 August 2026.",
    }
    values = [
        ExtractedValue(field_name="incident_date", value="10 August 2026", normalized_value="2026-08-10", confidence=0.97, source_lines=["page_1_line_1"], source_text=evidence["page_1_line_1"], semantic_reason="This sentence states when the accident occurred.", validation_status="VALID"),
        ExtractedValue(field_name="treatment_date", value="12 August 2026", normalized_value="2026-08-12", confidence=0.96, source_lines=["page_1_line_2"], source_text=evidence["page_1_line_2"], semantic_reason="This sentence states when treatment occurred.", validation_status="VALID"),
    ]
    result = validate_semantic_extraction(values, fields_for_document("claim_form"), evidence, ["incident_date"])
    assert [(item.field_name, item.normalized_value) for item in result] == [
        ("incident_date", "2026-08-10"), ("treatment_date", "2026-08-12")
    ]


def test_required_absent_field_is_missing_not_unclear_or_not_applicable():
    result = validate_semantic_extraction([], fields_for_document("claim_form"), {}, ["incident_date"])
    assert result[0].field_name == "incident_date"
    assert result[0].validation_status == "MISSING"


def test_numeric_ocr_dates_use_deterministic_cambodian_day_first_normalization():
    evidence = {"page_1_line_1": "Date of Service: 01/09/2026"}
    values = [ExtractedValue(
        field_name="service_date", value="01/09/2026", normalized_value="2026-01-09",
        confidence=0.95, source_lines=["page_1_line_1"], source_text=evidence["page_1_line_1"],
        semantic_reason="The label identifies a service date.", validation_status="VALID",
    )]
    result = validate_semantic_extraction(values, fields_for_document("invoice"), evidence, [])
    assert result[0].normalized_value == "2026-09-01"


def test_optional_missing_fields_are_omitted_from_document_ui_payload():
    values = [ExtractedValue(field_name="recommendations", value=None, validation_status="MISSING")]
    assert validate_semantic_extraction(values, fields_for_document("medical_report"), {}, []) == []


def test_medical_report_reference_cannot_become_invoice_number(monkeypatch):
    response = {"values": [
        {"field_name": "medical_report_number", "value": "SH-2024-01756", "normalized_value": "SH-2024-01756", "original_ocr_value": "SH-2024-01756", "confidence": 0.96, "source_lines": ["page_1_line_1"], "source_text": "Reference No: SH-2024-01756", "semantic_reason": "A report-header reference identifies the medical report.", "validation_status": "VALID"},
        {"field_name": "invoice_number", "value": "SH-2024-01756", "normalized_value": "SH-2024-01756", "original_ocr_value": "SH-2024-01756", "confidence": 0.5, "source_lines": ["page_1_line_1"], "source_text": "Reference No: SH-2024-01756", "semantic_reason": "Incorrect identifier type", "validation_status": "VALID"},
    ]}
    monkeypatch.setattr(llm_extraction, "_send_azure_chat", lambda *args, **kwargs: json.dumps(response))
    result = llm_extraction.extract_fields_from_ocr("medical_report", "Reference No: SH-2024-01756", Settings())
    assert [item.field_name for item in result.values] == ["medical_report_number"]


def test_incident_treatment_and_invoice_dates_use_chronology_not_equality():
    def field(name: str, value: str) -> ExtractedField:
        return ExtractedField(document_id=1, field_name=name, field_value=value, normalized_value=value, validation_status="VALID")

    fields = {
        "claim_form": {"incident_date": field("incident_date", "2026-08-10")},
        "medical_report": {"treatment_date": field("treatment_date", "2026-08-12")},
        "invoice": {"service_date": field("service_date", "2026-08-12"), "invoice_date": field("invoice_date", "2026-08-12")},
    }
    rules = _chronology_rules(fields)
    assert rules
    assert all(result == "match" for _, result, _ in rules)
    assert all("consistent_incident_date" not in name for name, _, _ in rules)
