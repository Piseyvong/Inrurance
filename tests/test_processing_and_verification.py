"""Tests for OCR, extraction, and deterministic verification."""

from datetime import date

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.models.claim import Claim
from app.models.document import Document
from app.models.extracted_field import ExtractedField
from app.models.ocr_run import OCRRun
from app.schemas.claim import ClaimCreate
from app.services.claim_service import create_claim_record, save_uploaded_document
from app.services.extraction_service import run_extraction_for_document
from app.services import llm_extraction
from app.services.llm_extraction import LLMServiceError, azure_openai_base_url, extract_fields_from_ocr, parse_llm_json, validate_azure_openai_settings
from app.services.ocr import OCRLineResult, OCRResult, process_document
from app.services.precheck_service import run_claim_precheck
from app.services.verification_service import list_officer_claims, run_verification
from tests.conftest import upload_file

PDF_BYTES = b"%PDF-1.4\nsynthetic"


class FakeOCRProvider:
    """Successful OCR provider used to avoid heavy OCR in unit tests."""

    engine_name = "fake_ocr"

    def __init__(self, text: str, confidence: float = 0.95) -> None:
        self.text = text
        self.confidence = confidence

    def extract(self, file_path):
        return OCRResult(
            engine=self.engine_name,
            engine_version="test",
            status="succeeded",
            raw_text=self.text,
            lines=[OCRLineResult(line_id="line_1", text=self.text, page_number=1, confidence=self.confidence)],
            average_confidence=self.confidence,
        )


class FailingOCRProvider:
    """Failing OCR provider used to confirm failed jobs are closed."""

    engine_name = "fake_ocr"

    def extract(self, file_path):
        return OCRResult(engine=self.engine_name, engine_version="test", status="failed", raw_text="", error_message="boom")


async def _claim_with_document(async_db_session, tmp_path, doc_type="claim_form") -> tuple[int, Document]:
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )
    document = await save_uploaded_document(
        claim.id,
        doc_type,
        upload_file(f"{doc_type}.pdf", PDF_BYTES, "application/pdf"),
        async_db_session,
        settings,
    )
    return claim.id, document


@pytest.mark.anyio
async def test_ocr_success_is_persisted(async_db_session, tmp_path):
    _claim_id, document = await _claim_with_document(async_db_session, tmp_path)

    run = await process_document(document.id, async_db_session, FakeOCRProvider("claimant_name: សុខា"))

    assert run.status == "succeeded"
    assert "សុខា" in run.raw_text


@pytest.mark.anyio
async def test_ocr_failure_does_not_remain_processing(async_db_session, tmp_path):
    claim_id, document = await _claim_with_document(async_db_session, tmp_path)

    run = await process_document(document.id, async_db_session, FailingOCRProvider())

    assert run.status == "failed"
    assert run.completed_at is not None
    assert (await async_db_session.get(Claim, claim_id)).status == "human_review_required"


@pytest.mark.anyio
async def test_low_confidence_ocr_routes_claim_to_human_review(async_db_session, tmp_path):
    claim_id, document = await _claim_with_document(async_db_session, tmp_path)

    run = await process_document(document.id, async_db_session, FakeOCRProvider("claimant_name: សុខា", confidence=0.44))

    assert run.status == "succeeded"
    assert float(run.average_confidence) < 0.70
    assert (await async_db_session.get(Claim, claim_id)).status == "human_review_required"


def test_malformed_llm_json_is_rejected():
    with pytest.raises(ValueError):
        parse_llm_json("{not-json")


def test_azure_openai_base_url_appends_openai_v1_once():
    assert azure_openai_base_url("https://example.openai.azure.com") == "https://example.openai.azure.com/openai/v1/"
    assert azure_openai_base_url("https://example.openai.azure.com/openai/v1/") == "https://example.openai.azure.com/openai/v1/"


def test_azure_openai_validation_reports_missing_settings():
    settings = Settings()
    settings.azure_openai_endpoint = ""
    settings.azure_openai_api_key = ""
    settings.azure_openai_deployment = ""

    with pytest.raises(LLMServiceError) as exc:
        validate_azure_openai_settings(settings)

    assert "AZURE_OPENAI_ENDPOINT" in exc.value.public_message
    assert "AZURE_OPENAI_API_KEY" in exc.value.public_message
    assert "AZURE_OPENAI_DEPLOYMENT" in exc.value.public_message


def test_azure_openai_extraction_uses_deployment_name(monkeypatch):
    settings = Settings()
    settings.azure_openai_endpoint = "https://example.openai.azure.com"
    settings.azure_openai_api_key = "test-key"
    settings.azure_openai_deployment = "claims-gpt-4o"
    seen = {}

    def fake_send(settings_arg, messages, max_tokens, json_response=False):
        seen["deployment"] = settings_arg.azure_openai_deployment
        seen["messages"] = messages
        return '{"values":[{"field_name":"claimant_name","field_value":"Sokha","supporting_line_refs":["line_1"],"validation_status":"valid"}]}'

    monkeypatch.setattr(llm_extraction, "_send_azure_chat", fake_send)

    result = extract_fields_from_ocr("claim_form", "claimant_name: Sokha", settings)

    assert result.method == "azure_openai:claims-gpt-4o"
    assert seen["deployment"] == "claims-gpt-4o"
    assert result.values[0].field_value == "Sokha"


def test_azure_openai_extraction_retries_schema_invalid_json(monkeypatch):
    settings = Settings()
    settings.azure_openai_endpoint = "https://example.openai.azure.com"
    settings.azure_openai_api_key = "test-key"
    settings.azure_openai_deployment = "claims-gpt-4o"
    responses = iter([
        '{"values":[{"field_name":"claimant_name"}]}',
        '{"values":[{"field_name":"claimant_name","field_value":"Sokha","supporting_line_refs":["line_1"],"validation_status":"valid"}]}',
    ])

    def fake_send(*_args, **_kwargs):
        return next(responses)

    monkeypatch.setattr(llm_extraction, "_send_azure_chat", fake_send)

    result = extract_fields_from_ocr("claim_form", "claimant_name: Sokha", settings)

    assert result.values[0].field_value == "Sokha"


@pytest.mark.anyio
async def test_missing_successful_ocr_blocks_extraction(async_db_session, tmp_path):
    _claim_id, document = await _claim_with_document(async_db_session, tmp_path)

    with pytest.raises(HTTPException) as exc:
        await run_extraction_for_document(document.id, async_db_session)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_extraction_preserves_khmer_unicode(async_db_session, tmp_path, monkeypatch):
    def fake_send(_settings_arg, _messages, max_tokens, json_response=False):
        return '{"values":[{"field_name":"claimant_name","field_value":"\\u179f\\u17bb\\u1781\\u17b6","supporting_line_refs":["line_1"],"validation_status":"valid"}]}'

    monkeypatch.setattr(llm_extraction, "_send_azure_chat", fake_send)

    _claim_id, document = await _claim_with_document(async_db_session, tmp_path)
    async_db_session.add(
        OCRRun(
            document_id=document.id,
            engine="fake",
            engine_version="test",
            status="succeeded",
            raw_text="claimant_name: សុខា\npolicy_number: POL-001\nincident_date: 2026-07-31\nclaimed_amount: 50.00",
        )
    )
    await async_db_session.commit()

    fields = await run_extraction_for_document(document.id, async_db_session)

    assert any(field.field_value == "សុខា" for field in fields)


@pytest.mark.anyio
async def test_verification_routes_missing_documents_to_waiting_for_documents(async_db_session):
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )

    report = await run_verification(claim.id, async_db_session)

    assert report["claim_status"] == "waiting_for_documents"
    assert "required_documents_present" in report["reasons_for_human_review"]


@pytest.mark.anyio
async def test_claim_precheck_requires_all_documents(async_db_session, tmp_path):
    claim_id, _document = await _claim_with_document(async_db_session, tmp_path, doc_type="claim_form")

    with pytest.raises(HTTPException) as exc:
        await run_claim_precheck(claim_id, async_db_session, FakeOCRProvider("ok"))

    assert exc.value.status_code == 400
    assert "medical_report" in exc.value.detail
    assert "invoice" in exc.value.detail


@pytest.mark.anyio
async def test_claim_precheck_extracts_documents_before_verification(async_db_session, tmp_path, monkeypatch):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )
    for doc_type in ["claim_form", "medical_report", "invoice"]:
        await save_uploaded_document(
            claim.id,
            doc_type,
            upload_file(f"{doc_type}.pdf", PDF_BYTES, "application/pdf"),
            async_db_session,
            settings,
        )

    def fake_send(_settings_arg, messages, max_tokens, json_response=False):
        prompt = messages[-1]["content"]
        if "Document type: claim_form" in prompt:
            return (
                '{"values":['
                '{"field_name":"claimant_name","field_value":"Demo User","supporting_line_refs":["line_1"],"validation_status":"valid"},'
                '{"field_name":"policy_number","field_value":"POL-001","supporting_line_refs":["line_1"],"validation_status":"valid"},'
                '{"field_name":"incident_date","field_value":"2026-07-31","supporting_line_refs":["line_1"],"validation_status":"valid"},'
                '{"field_name":"claim_amount","field_value":"49.99","supporting_line_refs":["line_1"],"validation_status":"valid"},'
                '{"field_name":"currency","field_value":"USD","supporting_line_refs":["line_1"],"validation_status":"valid"}]}'
            )
        if "Document type: medical_report" in prompt:
            return (
                '{"values":['
                '{"field_name":"patient_name","field_value":"Demo User","supporting_line_refs":["line_1"],"validation_status":"valid"},'
                '{"field_name":"treatment_date","field_value":"2026-07-31","supporting_line_refs":["line_1"],"validation_status":"valid"},'
                '{"field_name":"diagnosis","field_value":"Flu","supporting_line_refs":["line_1"],"validation_status":"valid"}]}'
            )
        return (
            '{"values":['
            '{"field_name":"provider_name","field_value":"Demo Clinic","supporting_line_refs":["line_1"],"validation_status":"valid"},'
            '{"field_name":"invoice_number","field_value":"INV-001","supporting_line_refs":["line_1"],"validation_status":"valid"},'
            '{"field_name":"total_amount","field_value":"49.99","supporting_line_refs":["line_1"],"validation_status":"valid"},'
            '{"field_name":"currency","field_value":"USD","supporting_line_refs":["line_1"],"validation_status":"valid"}]}'
        )

    monkeypatch.setattr(llm_extraction, "_send_azure_chat", fake_send)

    report = await run_claim_precheck(
        claim.id,
        async_db_session,
        FakeOCRProvider(
            "claimant_name: Demo User\npolicy_number: POL-001\nincident_date: 2026-07-31\nclaim_amount: 49.99\ncurrency: USD\n"
            "patient_name: Demo User\ntreatment_date: 2026-07-31\ndiagnosis: Flu\nprovider_name: Demo Clinic\ninvoice_number: INV-001\ntotal_amount: 49.99"
        ),
    )

    assert report["claim_status"] == "pending_human_review"
    assert len(report["documents"]) == 3
    assert len(report["extracted_fields"]) == 14


@pytest.mark.anyio
async def test_verification_detects_cross_document_mismatch(async_db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )
    docs = {
        doc_type: await save_uploaded_document(
            claim.id,
            doc_type,
            upload_file(f"{doc_type}.pdf", PDF_BYTES, "application/pdf"),
            async_db_session,
            settings,
        )
        for doc_type in ["claim_form", "medical_report", "invoice"]
    }
    async_db_session.add_all(
        [
            ExtractedField(document_id=docs["claim_form"].id, field_name="claimant_name", field_value="Alice", validation_status="valid"),
            ExtractedField(document_id=docs["claim_form"].id, field_name="policy_number", field_value="POL-001", validation_status="valid"),
            ExtractedField(document_id=docs["claim_form"].id, field_name="incident_date", field_value="2026-07-31", validation_status="valid"),
            ExtractedField(document_id=docs["claim_form"].id, field_name="claimed_amount", field_value="50.00", validation_status="valid"),
            ExtractedField(document_id=docs["medical_report"].id, field_name="patient_name", field_value="Bob", validation_status="valid"),
            ExtractedField(document_id=docs["medical_report"].id, field_name="incident_date", field_value="2026-07-31", validation_status="valid"),
            ExtractedField(document_id=docs["medical_report"].id, field_name="diagnosis", field_value="Flu", validation_status="valid"),
            ExtractedField(document_id=docs["invoice"].id, field_name="total_amount", field_value="50.00", validation_status="valid"),
        ]
    )
    await async_db_session.commit()

    report = await run_verification(claim.id, async_db_session)

    assert report["claim_status"] == "pending_human_review"
    assert "consistent_identity_claim_form_vs_medical_report" in report["reasons_for_human_review"]


@pytest.mark.anyio
async def test_clean_claim_under_50_is_auto_approved_by_deterministic_rule(async_db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31), claimed_amount="49.99"),
        async_db_session,
    )
    docs = {
        doc_type: await save_uploaded_document(
            claim.id,
            doc_type,
            upload_file(f"{doc_type}.pdf", PDF_BYTES, "application/pdf"),
            async_db_session,
            settings,
        )
        for doc_type in ["claim_form", "medical_report", "invoice"]
    }
    ocr_runs = {}
    for document in docs.values():
        ocr_run = OCRRun(document_id=document.id, engine="fake", status="succeeded", raw_text="ok", average_confidence=0.95)
        async_db_session.add(ocr_run)
        ocr_runs[document.doc_type] = ocr_run
    await async_db_session.flush()
    async_db_session.add_all(
        [
            ExtractedField(document_id=docs["claim_form"].id, ocr_run_id=ocr_runs["claim_form"].id, field_name="claimant_name", field_value="Demo User", validation_status="valid"),
            ExtractedField(document_id=docs["claim_form"].id, ocr_run_id=ocr_runs["claim_form"].id, field_name="policy_number", field_value="POL-001", validation_status="valid"),
            ExtractedField(document_id=docs["claim_form"].id, ocr_run_id=ocr_runs["claim_form"].id, field_name="incident_date", field_value="2026-07-31", validation_status="valid"),
            ExtractedField(document_id=docs["claim_form"].id, ocr_run_id=ocr_runs["claim_form"].id, field_name="claim_amount", field_value="49.99", validation_status="valid"),
            ExtractedField(document_id=docs["claim_form"].id, ocr_run_id=ocr_runs["claim_form"].id, field_name="currency", field_value="USD", validation_status="valid"),
            ExtractedField(document_id=docs["medical_report"].id, ocr_run_id=ocr_runs["medical_report"].id, field_name="patient_name", field_value="Demo User", validation_status="valid"),
            ExtractedField(document_id=docs["medical_report"].id, ocr_run_id=ocr_runs["medical_report"].id, field_name="treatment_date", field_value="2026-07-31", validation_status="valid"),
            ExtractedField(document_id=docs["medical_report"].id, ocr_run_id=ocr_runs["medical_report"].id, field_name="diagnosis", field_value="Flu", validation_status="valid"),
            ExtractedField(document_id=docs["invoice"].id, ocr_run_id=ocr_runs["invoice"].id, field_name="provider_name", field_value="Demo Clinic", validation_status="valid"),
            ExtractedField(document_id=docs["invoice"].id, ocr_run_id=ocr_runs["invoice"].id, field_name="invoice_number", field_value="INV-001", validation_status="valid"),
            ExtractedField(document_id=docs["invoice"].id, ocr_run_id=ocr_runs["invoice"].id, field_name="total_amount", field_value="49.99", validation_status="valid"),
            ExtractedField(document_id=docs["invoice"].id, ocr_run_id=ocr_runs["invoice"].id, field_name="currency", field_value="USD", validation_status="valid"),
        ]
    )
    await async_db_session.commit()

    report = await run_verification(claim.id, async_db_session)

    assert report["claim_status"] == "auto_approved"
    assert report["reasons_for_human_review"] == []
    assert any(rule.rule_name == "configured_auto_approval_threshold" and rule.result == "match" for rule in report["rule_results"])


@pytest.mark.anyio
async def test_officer_queue_lists_human_review_claims_only(async_db_session):
    review_claim = await create_claim_record(
        ClaimCreate(claimant_name="Review User", policy_number="POL-REVIEW", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )
    auto_claim = await create_claim_record(
        ClaimCreate(claimant_name="Auto User", policy_number="POL-AUTO", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )
    review_claim.status = "human_review_required"
    auto_claim.status = "auto_approved"
    await async_db_session.commit()

    queue = await list_officer_claims(async_db_session)

    assert [claim.id for claim in queue] == [review_claim.id]
