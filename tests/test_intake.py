"""Tests for claim intake and document upload safety."""

from datetime import date

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.models.audit_log import AuditLog
from app.schemas.claim import ClaimCreate
from app.services.claim_service import (
    build_claim_response,
    create_claim_record,
    get_claim_or_404,
    save_uploaded_document,
)
from tests.conftest import upload_file

PDF_BYTES = b"%PDF-1.4\nsynthetic"
PNG_BYTES = b"\x89PNG\r\n\x1a\nsynthetic"
JPG_BYTES = b"\xff\xd8\xff\xe0synthetic"
EXE_BYTES = b"MZ\x00\x00not an image"


def test_claim_creation_writes_audit_event(db_session):
    claim = create_claim_record(
        ClaimCreate(
            claimant_name="Sokha Demo",
            policy_number="POL-001",
            incident_date=date(2026, 7, 31),
        ),
        db_session,
    )

    audit = db_session.query(AuditLog).filter(AuditLog.claim_id == claim.id).one()
    assert claim.status == "intake"
    assert audit.actor == "system"
    assert audit.action == "claim_created"


def test_invalid_claim_id_returns_404(db_session):
    with pytest.raises(HTTPException) as exc:
        get_claim_or_404(999, db_session)
    assert exc.value.status_code == 404


def test_valid_document_upload_stores_metadata_and_audit(db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", incident_date=date(2026, 7, 31)),
        db_session,
    )

    document = save_uploaded_document(
        claim.id,
        "claim_form",
        upload_file("claim form.pdf", PDF_BYTES, "application/pdf"),
        db_session,
        settings,
    )

    audit = db_session.query(AuditLog).filter(AuditLog.action == "document_uploaded").one()
    assert document.original_filename == "claim_form.pdf"
    assert document.mime_type == "application/pdf"
    assert document.file_size == len(PDF_BYTES)
    assert audit.details == "claim_form"


def test_invalid_document_type_returns_400(db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", incident_date=date(2026, 7, 31)),
        db_session,
    )

    with pytest.raises(HTTPException) as exc:
        save_uploaded_document(claim.id, "id_card", upload_file("x.pdf", PDF_BYTES, "application/pdf"), db_session, settings)
    assert exc.value.status_code == 400


def test_disguised_executable_with_image_extension_is_rejected(db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", incident_date=date(2026, 7, 31)),
        db_session,
    )

    with pytest.raises(HTTPException) as exc:
        save_uploaded_document(claim.id, "receipt", upload_file("receipt.png", EXE_BYTES, "image/png"), db_session, settings)
    assert exc.value.status_code == 400


def test_oversized_file_is_rejected(db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    settings.max_upload_bytes = 8
    claim = create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", incident_date=date(2026, 7, 31)),
        db_session,
    )

    with pytest.raises(HTTPException) as exc:
        save_uploaded_document(claim.id, "receipt", upload_file("receipt.pdf", PDF_BYTES, "application/pdf"), db_session, settings)
    assert exc.value.status_code == 400


def test_duplicate_document_type_is_rejected(db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", incident_date=date(2026, 7, 31)),
        db_session,
    )
    save_uploaded_document(claim.id, "claim_form", upload_file("a.pdf", PDF_BYTES, "application/pdf"), db_session, settings)

    with pytest.raises(HTTPException) as exc:
        save_uploaded_document(claim.id, "claim_form", upload_file("b.pdf", PDF_BYTES, "application/pdf"), db_session, settings)
    assert exc.value.status_code == 400


def test_path_traversal_filename_is_sanitized(db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", incident_date=date(2026, 7, 31)),
        db_session,
    )

    document = save_uploaded_document(
        claim.id,
        "receipt",
        upload_file("..\\..\\receipt.pdf", PDF_BYTES, "application/pdf"),
        db_session,
        settings,
    )
    assert ".." not in document.original_filename
    assert str(settings.upload_dir.resolve()) in document.file_path


def test_document_completeness_lists_missing_types(db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", incident_date=date(2026, 7, 31)),
        db_session,
    )
    save_uploaded_document(claim.id, "claim_form", upload_file("a.pdf", PDF_BYTES, "application/pdf"), db_session, settings)

    response = build_claim_response(get_claim_or_404(claim.id, db_session, include_documents=True))
    assert response["document_completeness"]["is_complete"] is False
    assert set(response["missing_required_document_types"]) == {"medical_report", "receipt"}
