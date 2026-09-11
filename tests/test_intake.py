"""Tests for claim intake and document upload safety."""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

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


@pytest.mark.anyio
async def test_claim_creation_writes_audit_event(async_db_session):
    claim = await create_claim_record(
        ClaimCreate(
            claimant_name="Sokha Demo", claim_type="medical",
            policy_number="POL-001",
            incident_date=date(2026, 7, 31),
        ),
        async_db_session,
    )

    audit = (await async_db_session.execute(select(AuditLog).where(AuditLog.claim_id == claim.id))).scalar_one()
    assert claim.status == "intake"
    assert audit.actor == "system"
    assert audit.action == "claim_created"


@pytest.mark.anyio
async def test_invalid_claim_id_returns_404(async_db_session):
    with pytest.raises(HTTPException) as exc:
        await get_claim_or_404(999, async_db_session)
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_valid_document_upload_stores_metadata_and_audit(async_db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )

    document = await save_uploaded_document(
        claim.id,
        "claim_form",
        upload_file("claim form.pdf", PDF_BYTES, "application/pdf"),
        async_db_session,
        settings,
    )

    audit = (await async_db_session.execute(select(AuditLog).where(AuditLog.action == "document_uploaded"))).scalar_one()
    assert document.original_filename == "claim_form.pdf"
    assert document.mime_type == "application/pdf"
    assert document.file_size == len(PDF_BYTES)
    assert audit.details == "claim_form"


@pytest.mark.anyio
async def test_invalid_document_type_returns_400(async_db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )

    with pytest.raises(HTTPException) as exc:
        await save_uploaded_document(claim.id, "id_card", upload_file("x.pdf", PDF_BYTES, "application/pdf"), async_db_session, settings)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_disguised_executable_with_image_extension_is_rejected(async_db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )

    with pytest.raises(HTTPException) as exc:
        await save_uploaded_document(claim.id, "invoice", upload_file("invoice.png", EXE_BYTES, "image/png"), async_db_session, settings)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_oversized_file_is_rejected(async_db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    settings.max_upload_bytes = 8
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )

    with pytest.raises(HTTPException) as exc:
        await save_uploaded_document(claim.id, "invoice", upload_file("invoice.pdf", PDF_BYTES, "application/pdf"), async_db_session, settings)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_duplicate_document_type_is_rejected(async_db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )
    await save_uploaded_document(claim.id, "claim_form", upload_file("a.pdf", PDF_BYTES, "application/pdf"), async_db_session, settings)

    with pytest.raises(HTTPException) as exc:
        await save_uploaded_document(claim.id, "claim_form", upload_file("b.pdf", PDF_BYTES, "application/pdf"), async_db_session, settings)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_path_traversal_filename_is_sanitized(async_db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )

    document = await save_uploaded_document(
        claim.id,
        "invoice",
        upload_file("..\\..\\invoice.pdf", PDF_BYTES, "application/pdf"),
        async_db_session,
        settings,
    )
    assert ".." not in document.original_filename
    assert str(settings.upload_dir.resolve()) in document.file_path


@pytest.mark.anyio
async def test_document_completeness_lists_missing_types(async_db_session, tmp_path):
    settings = Settings()
    settings.upload_dir = tmp_path / "uploads"
    claim = await create_claim_record(
        ClaimCreate(claimant_name="Demo User", policy_number="POL-001", claim_type="medical", incident_date=date(2026, 7, 31)),
        async_db_session,
    )
    await save_uploaded_document(claim.id, "claim_form", upload_file("a.pdf", PDF_BYTES, "application/pdf"), async_db_session, settings)

    response = await build_claim_response(
        await get_claim_or_404(claim.id, async_db_session, include_documents=True),
        async_db_session,
    )
    assert response["document_completeness"]["is_complete"] is False
    assert set(response["missing_required_document_types"]) == {"invoice", "medical_report"}
