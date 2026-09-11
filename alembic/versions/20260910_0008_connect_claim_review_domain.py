"""connect customer policies, evidence, OCR, and officer review

Revision ID: 20260910_0008
Revises: 20260904_0007
"""
from alembic import op
import sqlalchemy as sa

revision = "20260910_0008"
down_revision = "20260904_0007"
branch_labels = None
depends_on = None


def _columns(inspector, table):
    return {column["name"] for column in inspector.get_columns(table)}


def _add(table, column, existing):
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "policy_documents" not in tables:
        op.create_table("policy_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("insurance_product_id", sa.Integer(), sa.ForeignKey("insurance_products.id"), nullable=False),
            sa.Column("policy_name", sa.String(180), nullable=False), sa.Column("product_category", sa.String(50), nullable=False),
            sa.Column("policy_code", sa.String(80), nullable=False), sa.Column("version", sa.String(50), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=False), sa.Column("expiry_date", sa.Date()),
            sa.Column("language", sa.String(30), nullable=False, server_default="Khmer-English"),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("original_filename", sa.String(255), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False), sa.Column("extracted_text", sa.Text(), nullable=False),
            sa.Column("required_documents", sa.JSON(), nullable=False, server_default="[]"), sa.Column("configured_rules", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    inspector = sa.inspect(bind)
    policy_document_columns = _columns(inspector, "policy_documents")
    _add("policy_documents", sa.Column("required_documents", sa.JSON(), server_default="[]"), policy_document_columns)
    _add("policy_documents", sa.Column("configured_rules", sa.JSON(), server_default="{}"), policy_document_columns)
    if "policy_chunks" not in tables:
        op.create_table("policy_chunks", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("policy_document_id", sa.Integer(), sa.ForeignKey("policy_documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section", sa.String(255)), sa.Column("page_number", sa.Integer()),
            sa.Column("content", sa.Text(), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False))

    for table, columns in {
        "users": [sa.Column("phone", sa.String(60)), sa.Column("updated_at", sa.DateTime(timezone=True))],
        "insurance_products": [sa.Column("updated_at", sa.DateTime(timezone=True))],
        "policies": [sa.Column("policy_template_id", sa.Integer()), sa.Column("coverage_limit", sa.Numeric(14,2)), sa.Column("deductible", sa.Numeric(14,2)), sa.Column("currency", sa.String(3), server_default="USD"), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True))],
        "claims": [sa.Column("claim_number", sa.String(40)), sa.Column("currency", sa.String(3), server_default="USD"), sa.Column("review_status", sa.String(50)), sa.Column("updated_at", sa.DateTime(timezone=True))],
        "documents": [sa.Column("uploaded_by_user_id", sa.Integer()), sa.Column("stored_filename", sa.String(255)), sa.Column("ocr_status", sa.String(30), server_default="pending"), sa.Column("extraction_status", sa.String(30), server_default="pending"), sa.Column("verification_status", sa.String(30), server_default="pending"), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True))],
        "ocr_runs": [sa.Column("cleaned_text", sa.Text()), sa.Column("language", sa.String(30), server_default="khm+eng")],
        "extracted_fields": [sa.Column("original_ocr_value", sa.Text()), sa.Column("officer_corrected_value", sa.Text()), sa.Column("officer_corrected_by", sa.Integer()), sa.Column("officer_corrected_at", sa.DateTime(timezone=True))],
        "audit_log": [sa.Column("user_id", sa.Integer()), sa.Column("actor_role", sa.String(30)), sa.Column("entity_type", sa.String(50)), sa.Column("entity_id", sa.Integer()), sa.Column("old_value", sa.Text()), sa.Column("new_value", sa.Text())],
    }.items():
        existing = _columns(inspector, table)
        for column in columns:
            _add(table, column, existing)

    if "officer_notes" not in tables:
        op.create_table("officer_notes", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
            sa.Column("officer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("note", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_table("officer_notes")
    for table, names in {"audit_log":["new_value","old_value","entity_id","entity_type","actor_role","user_id"], "extracted_fields":["officer_corrected_at","officer_corrected_by","officer_corrected_value","original_ocr_value"], "ocr_runs":["language","cleaned_text"], "documents":["updated_at","created_at","verification_status","extraction_status","ocr_status","stored_filename","uploaded_by_user_id"], "claims":["updated_at","review_status","currency","claim_number"], "policies":["updated_at","created_at","currency","deductible","coverage_limit","policy_template_id"], "insurance_products":["updated_at"], "users":["updated_at","phone"]}.items():
        for name in names: op.drop_column(table, name)
    op.drop_table("policy_chunks")
    op.drop_table("policy_documents")
