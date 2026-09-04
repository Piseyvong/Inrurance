"""add customer portal, products, checks, and decisions

Revision ID: 20260903_0006
Revises: 20260903_0005
"""
from alembic import op
import sqlalchemy as sa

revision = "20260903_0006"
down_revision = "20260903_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False), sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False, server_default="customer"), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("email"))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("insurance_products",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(180), nullable=False),
        sa.Column("product_type", sa.String(50), nullable=False), sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text()), sa.Column("policy_document_path", sa.String(500)), sa.Column("policy_document_version", sa.String(50)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("effective_from", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("code", "version", name="uq_product_code_version"))
    op.create_index("ix_insurance_products_code", "insurance_products", ["code"])
    op.create_index("ix_insurance_products_product_type", "insurance_products", ["product_type"])
    op.create_table("policy_rules", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("insurance_product_id", sa.Integer(), sa.ForeignKey("insurance_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_type", sa.String(80), nullable=False), sa.Column("name", sa.String(180), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False), sa.Column("clause_reference", sa.String(255)),
        sa.Column("status", sa.String(30), nullable=False, server_default="confirmed"))
    op.create_table("policies", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("policy_number", sa.String(100), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("insurance_product_id", sa.Integer(), sa.ForeignKey("insurance_products.id"), nullable=False),
        sa.Column("product_version", sa.Integer(), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False))
    # Keep SQLite local-demo migrations portable; ORM relationships still
    # enforce ownership in application services.
    op.add_column("claims", sa.Column("user_id", sa.Integer()))
    op.add_column("claims", sa.Column("customer_policy_id", sa.Integer()))
    op.add_column("claims", sa.Column("insurance_product_id", sa.Integer()))
    op.add_column("claims", sa.Column("description", sa.Text()))
    op.add_column("claims", sa.Column("risk_score", sa.Integer()))
    op.add_column("claims", sa.Column("risk_band", sa.String(30)))
    op.add_column("claims", sa.Column("recommendation", sa.Text()))
    op.add_column("documents", sa.Column("file_hash", sa.String(64)))
    op.add_column("documents", sa.Column("reference_number", sa.String(120)))
    op.create_table("claim_checks", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(60), nullable=False), sa.Column("check_name", sa.String(120), nullable=False), sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("score", sa.Integer()), sa.Column("evidence", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("decisions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome", sa.String(50), nullable=False), sa.Column("recommended_amount", sa.Numeric(14,2)), sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("authority", sa.String(30), nullable=False), sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("final", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))


def downgrade() -> None:
    op.drop_table("decisions"); op.drop_table("claim_checks")
    for column in ["reference_number", "file_hash"]: op.drop_column("documents", column)
    for column in ["recommendation", "risk_band", "risk_score", "description", "insurance_product_id", "customer_policy_id", "user_id"]: op.drop_column("claims", column)
    op.drop_table("policies"); op.drop_table("policy_rules"); op.drop_table("insurance_products"); op.drop_table("users")
