"""create phase 1 tables

Revision ID: 20260729_0001
Revises:
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claimant_name", sa.String(length=255), nullable=False),
        sa.Column("policy_number", sa.String(length=100), nullable=False),
        sa.Column("claim_type", sa.String(length=50), nullable=False),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("claimed_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_claims_id"), "claims", ["id"], unique=False)
    op.create_index(op.f("ix_claims_policy_number"), "claims", ["policy_number"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("doc_type", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_claim_id"), "documents", ["claim_id"], unique=False)
    op.create_index(op.f("ix_documents_id"), "documents", ["id"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_claim_id"), "audit_log", ["claim_id"], unique=False)
    op.create_index(op.f("ix_audit_log_id"), "audit_log", ["id"], unique=False)

    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("field_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_extracted_fields_document_id"), "extracted_fields", ["document_id"], unique=False)
    op.create_index(op.f("ix_extracted_fields_id"), "extracted_fields", ["id"], unique=False)

    op.create_table(
        "rule_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("rule_name", sa.String(length=100), nullable=False),
        sa.Column("result", sa.String(length=50), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rule_results_claim_id"), "rule_results", ["claim_id"], unique=False)
    op.create_index(op.f("ix_rule_results_id"), "rule_results", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rule_results_id"), table_name="rule_results")
    op.drop_index(op.f("ix_rule_results_claim_id"), table_name="rule_results")
    op.drop_table("rule_results")

    op.drop_index(op.f("ix_extracted_fields_id"), table_name="extracted_fields")
    op.drop_index(op.f("ix_extracted_fields_document_id"), table_name="extracted_fields")
    op.drop_table("extracted_fields")

    op.drop_index(op.f("ix_audit_log_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_claim_id"), table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index(op.f("ix_documents_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_claim_id"), table_name="documents")
    op.drop_table("documents")

    op.drop_index(op.f("ix_claims_policy_number"), table_name="claims")
    op.drop_index(op.f("ix_claims_id"), table_name="claims")
    op.drop_table("claims")
