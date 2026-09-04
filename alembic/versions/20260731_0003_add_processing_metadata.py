"""add document processing metadata

Revision ID: 20260731_0003
Revises: 20260730_0002
Create Date: 2026-07-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_0003"
down_revision: Union[str, None] = "20260730_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("original_filename", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("mime_type", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("file_size", sa.BigInteger(), nullable=True))
        batch_op.create_unique_constraint("uq_documents_claim_doc_type", ["claim_id", "doc_type"])

    op.create_table(
        "ocr_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("engine", sa.String(length=100), nullable=False),
        sa.Column("engine_version", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("average_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ocr_runs_document_id"), "ocr_runs", ["document_id"], unique=False)
    op.create_index(op.f("ix_ocr_runs_id"), "ocr_runs", ["id"], unique=False)

    with op.batch_alter_table("extracted_fields") as batch_op:
        batch_op.add_column(sa.Column("ocr_run_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("supporting_line_refs", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("extraction_method", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("validation_status", sa.String(length=50), nullable=True))
        batch_op.alter_column("field_value", existing_type=sa.Text(), nullable=True)
        batch_op.create_foreign_key("fk_extracted_fields_ocr_run_id_ocr_runs", "ocr_runs", ["ocr_run_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index(op.f("ix_extracted_fields_ocr_run_id"), ["ocr_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_extracted_fields_ocr_run_id"), table_name="extracted_fields")
    op.drop_constraint("fk_extracted_fields_ocr_run_id_ocr_runs", "extracted_fields", type_="foreignkey")
    op.alter_column(
        "extracted_fields",
        "field_value",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_column("extracted_fields", "validation_status")
    op.drop_column("extracted_fields", "extraction_method")
    op.drop_column("extracted_fields", "supporting_line_refs")
    op.drop_column("extracted_fields", "ocr_run_id")

    op.drop_index(op.f("ix_ocr_runs_id"), table_name="ocr_runs")
    op.drop_index(op.f("ix_ocr_runs_document_id"), table_name="ocr_runs")
    op.drop_table("ocr_runs")

    op.drop_constraint("uq_documents_claim_doc_type", "documents", type_="unique")
    op.drop_column("documents", "file_size")
    op.drop_column("documents", "mime_type")
    op.drop_column("documents", "original_filename")
